"""
Module implementing all jwt security logic
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose import JWTError
from passlib.context import CryptContext
from sqladmin.authentication import AuthenticationBackend
from sqlmodel import col
from sqlmodel import select
from sqlmodel import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ecodev_core.app_user import AppUser
from ecodev_core.auth_configuration import AUTH
from ecodev_core.db_connection import engine
from ecodev_core.logger import logger_get
from ecodev_core.permissions import Permission
from ecodev_core.pydantic_utils import Frozen


SCHEME = OAuth2PasswordBearer(tokenUrl='login')
auth_router = APIRouter(tags=['authentication'])
CONTEXT = CryptContext(schemes=['bcrypt'], deprecated='auto')
MONITORING = 'monitoring'
MONITORING_ERROR = 'Could not validate credentials. You need to be the monitoring user to call this'
INVALID_USER = 'Invalid User'
INVALID_TFA = 'Invalid TFA code'
ADMIN_ERROR = 'Could not validate credentials. You need admin rights to call this'
INVALID_CREDENTIALS = 'Invalid Credentials'
log = logger_get(__name__)


class Token(Frozen):
    """
    Simple class for storing token value and type
    """
    access_token: str
    token_type: str


class TokenData(Frozen):
    """
    Simple class storing token id information
    """
    id: int


def get_access_token(token: Dict[str, Any]):
    """
    Robust method to return access token or None
    """
    try:
        return token.get('token', {}).get('access_token')
    except AttributeError:
        return None


def get_app_services(user: AppUser, session: Session) -> List[str]:
    """
    Retrieve all app services the passed user has access to
    """
    if db_user := session.exec(select(AppUser).where(col(AppUser.id) == user.id)).first():
        return [right.app_service for right in db_user.rights]
    return []


class JwtAuth(AuthenticationBackend):
    """
    Sqladmin security class. Implement login/logout procedure as well as the authentication check.
    """

    async def login(self, request: Request) -> bool:
        """
        Login procedure: factorized with the fastapi jwt logic
        """
        form = await request.form()
        if token := self.authorized(form):
            request.session.update(token)
        return True if token else False

    def authorized(self, form: Any):
        """
        Check that the user information contained in the form corresponds to an admin user
        """
        with Session(engine) as session:
            try:
                return self.admin_token(form, session)
            except HTTPException:
                return None

    def admin_token(self, form: Any, session: Session) -> Union[Dict[str, str], None]:
        """
        Unsafe attempt to retrieve the token, only return it if admin rights
        """
        token = attempt_to_log(form.get('username', ''), form.get('password', ''), session)
        return token if is_admin_user(token['access_token']) else None

    async def logout(self, request: Request) -> bool:
        """
        Logout procedure: clears the cache
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        """
        Authentication procedure
        """
        return (token := request.session.get('access_token')) and is_admin_user(token)


def attempt_to_log(user: str,
                   password: str,
                   session: Session,
                   tfa_value: Optional[str] = None
                   ) -> Union[Dict, HTTPException]:
    """
    Factorized security logic. Ensure that the user is a legit one with a valid password.
    If so, generate a token (with or without encoded tfa_value depending on whether this argument is
    passed as an argument). If not, returns an HTTP exception with an intelligible error message.

    Attributes are:
        user: the user as expected to be found in the AppUser db
        password: the plain password, to be compared with the hashed one in the AppUser db
        session: db connection
        tfa_value: if filled, add it encoded to the generated token
    """
    selector = select(AppUser).where(col(AppUser.user) == user)
    if not (db_user := session.exec(selector).first()):
        log.warning('unauthorized user')
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=INVALID_USER)
    if not _check_password(password, db_user.password):
        log.warning('invalid user')
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=INVALID_CREDENTIALS)

    return {'access_token': _create_access_token(data={'user_id': db_user.id}, tfa_value=tfa_value),
            'token_type': 'bearer'}


def is_authorized_user(token: str = Depends(SCHEME)) -> bool:
    """
    Check if the passed token corresponds to an authorized user
    """
    try:
        return get_current_user(token) is not None
    except Exception:
        return False


def safe_get_user(token: Dict, tfa_check: bool = False) -> Union[AppUser, None]:
    """
    Safe method returning a user if one found given the passed token
    """
    try:
        return get_user(get_access_token(token), token['tfa'] if tfa_check else None, tfa_check)
    except (HTTPException, AttributeError):
        return None


def get_user(token: str = Depends(SCHEME),
             tfa_value: Optional[str] = None,
             tfa_check: bool = False) -> AppUser:
    """
    Retrieves (if it exists) the db user corresponding to the passed token
    """
    if user := get_current_user(token, tfa_value, tfa_check):
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS,
                        headers={'WWW-Authenticate': 'Bearer'})


def get_current_user(token: str,
                     tfa_value: Optional[str] = None,
                     tfa_check: bool = False
                     ) -> Union[AppUser, None]:
    """
    Retrieves (if it exists) a valid (meaning who has valid credentials) user from the db
    """
    token = _verify_access_token(token, tfa_value, tfa_check)
    with Session(engine) as session:
        return session.exec(select(AppUser).where(col(AppUser.id) == token.id)).first()


def is_admin_user(token: str = Depends(SCHEME)) -> AppUser:
    """
    Retrieves (if it exists) the admin (meaning who has valid credentials) user from the db
    """
    if (user := get_current_user(token)) and user.permission == Permission.ADMIN:
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ADMIN_ERROR,
                        headers={'WWW-Authenticate': 'Bearer'})


def is_monitoring_user(token: str = Depends(SCHEME)) -> AppUser:
    """
    Retrieves (if it exists) the monitoring user from the db
    """
    if (user := get_current_user(token)) and user.user == MONITORING:
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=MONITORING_ERROR, headers={'WWW-Authenticate': 'Bearer'})


def upsert_new_user(token: str, user: str, password: str = '') -> None:
    """
    Upsert a new user if not already present in db.

    NB: this method RAISES a http error if he token is invalid
    """
    user_id = _verify_access_token(token).id
    with Session(engine) as session:
        if not session.exec(select(AppUser).where(col(AppUser.id) == user_id)).first():
            session.add(AppUser(user=user, password=password, permission=Permission.Consultant,
                                id=user_id))
            session.commit()


def _create_access_token(data: Dict, tfa_value: Optional[str] = None) -> str:
    """
    Create an access token out of the passed data. Only called if credentials are valid
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=AUTH.access_token_expire_minutes)
    to_encode['exp'] = expire
    if tfa_value:
        to_encode['tfa'] = _hash_password(tfa_value)
    return jwt.encode(to_encode, AUTH.secret_key, algorithm=AUTH.algorithm)


def _verify_access_token(token: str,
                         tfa_value: Optional[str] = None,
                         tfa_check: bool = False) -> TokenData:
    """
    Retrieves the token data associated to the passed token if it contains valid credential info.
    """
    try:
        payload = jwt.decode(token, AUTH.secret_key, algorithms=[AUTH.algorithm])
        if tfa_check and (not tfa_value or not _check_password(tfa_value, payload.get('tfa'))):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_TFA,
                                headers={'WWW-Authenticate': 'Bearer'})
        if (user_id := payload.get('user_id')) is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_USER,
                                headers={'WWW-Authenticate': 'Bearer'})
        return TokenData(id=user_id)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS,
                            headers={'WWW-Authenticate': 'Bearer'}) from e


def _hash_password(password: str) -> str:
    """
    Hashes the passed password (encoding).
    """
    return CONTEXT.hash(password)


def _check_password(plain_password: Optional[str], hashed_password: str) -> bool:
    """
    Check the passed password (compare it to the passed encoded one).
    """
    return CONTEXT.verify(plain_password, hashed_password)

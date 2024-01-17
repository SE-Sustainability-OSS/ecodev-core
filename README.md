# ecodev-core

<p align="center">
<a href="https://github.com/FR-PAR-ECOACT/ecodev-core/actions" target="_blank">
    <img src="https://github.com/FR-PAR-ECOACT/ecodev-core/blob/main/badges/coverage.svg" alt="Coverage">
</a>
<a href="https://github.com/FR-PAR-ECOACT/ecodev-core/actions" target="_blank">
    <img src="https://github.com/FR-PAR-ECOACT/ecodev-core/blob/main/badges/pylint.svg" alt="Publish">
</a>
<a href="https://github.com/FR-PAR-ECOACT/ecodev-core/actions/workflows/code-quality.yml/badge.svg" target="_blank">
    <img src="https://github.com/FR-PAR-ECOACT/ecodev-core/actions/workflows/code-quality.yml/badge.svg" alt="Package version">
</a>
</p>

Low level ecoact generic code. Aimed at being published in open source with poetry

## Installation of this package

You are strongly encouraged to install this package via Docker.

Starting from a project with a Docker file:
* add the module ecodev-core in the `requirements.txt` file
* make sure the `.env` file includes all required fields (see `BaseSettings` and `AuthenticationConfiguration`)
* build the new version of the Docker container (typically `docker build --tag xxx .`)
* run it with docker compose (`dc up -d`).

## Documentation

Please find it in the [associated mkdoc website!](https://ecodev-doc.lcabox.com/)

# Line 1 to 20 are here to render the help output pretty, not to be read and even less understood!! :)
GREEN  := $(shell tput -Txterm setaf 2)
WHITE  := $(shell tput -Txterm setaf 7)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)
# From https://gist.github.com/prwhite/8168133#gistcomment-1727513
# Add the following 'help' target to your Makefile
# And add help text after each target name starting with ##
# A category can be added with @category
HELP_DESCRIPTION = \
    %help; \
    while(<>) { push @{$$help{$$2 // 'options'}}, [$$1, $$3] if /^([a-zA-Z\-]+)\s*:.*\#\#(?:@([a-zA-Z\-]+))?\s(.*)$$/ }; \
    print "usage: make [target]\n\n"; \
    for (sort keys %help) { \
    print "${WHITE}$$_:${RESET}\n"; \
    for (@{$$help{$$_}}) { \
    $$sep = " " x (32 - length $$_->[0]); \
    print "  ${YELLOW}$$_->[0]${RESET}$$sep${GREEN}$$_->[1]${RESET}\n"; \
    }; \
    print "\n"; }


help:		## Show this help.
	@perl -e '$(HELP_DESCRIPTION)' $(MAKEFILE_LIST)

jupyter:            ##@docker Launch a jupyter notebook from a fresh container
	docker exec ecodev_core  jupyter notebook --no-browser --ip 0.0.0.0 --allow-root --port 5000

build:           ##@docker Build a new prod docker image
	docker build --tag ecodev_core .

dev-build:           ##@docker Build a new development docker image
	docker build --tag ecodev_core . -f Dockerfile-dev

all-tests:		##@tests Run all the tests
	docker exec ecodev_core python3 -m unittest discover tests

prod-launch:            ##@docker Launch production containers
	docker-compose -f docker-compose.yml up -d

publish:           ##@poetry Build and publish a new patched ecodev_core version
	python3 -m poetry version patch
	python3 -m poetry build
	python3 -m poetry publish

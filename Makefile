.PHONY: dev lint test test-integration cov migrate seed

dev:
	uv run poe dev

lint:
	uv run poe lint

test:
	uv run poe test

test-integration:
	uv run poe test-integration

cov:
	uv run poe cov

migrate:
	uv run poe migrate

seed:
	uv run poe seed
## [0.4.6](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.5...v0.4.6) (2026-07-07)

## [0.4.5](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.4...v0.4.5) (2026-07-02)

## [0.4.4](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.3...v0.4.4) (2026-06-16)

## [0.4.3](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.2...v0.4.3) (2026-06-11)

## [0.4.2](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.1...v0.4.2) (2026-06-10)

## [0.4.1](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.4.0...v0.4.1) (2026-06-04)

### ♻️ Refactoring

* **rabbitmq:** sizing presets keyed on real drivers; small watermark 2GB ([72a2dee](https://github.com/bauer-group/CS-RabbitMQ/commit/72a2deeec2bd6d79fc5de32cea1a7e762d10ba67))

## [0.4.0](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.3.2...v0.4.0) (2026-06-04)

### 🚀 Features

* **rabbitmq:** raised max message size default to 256 MiB, documented sizing ([a75291b](https://github.com/bauer-group/CS-RabbitMQ/commit/a75291bc0a230eeef8366c5cf6694390abb0494c))

## [0.3.2](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.3.1...v0.3.2) (2026-06-04)

### ♻️ Refactoring

* **rabbitmq-init:** dropped the redundant baked default config ([7154ca2](https://github.com/bauer-group/CS-RabbitMQ/commit/7154ca2b5bcfc7f933509440c884a40c295cf2e0))

## [0.3.1](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.3.0...v0.3.1) (2026-06-04)

## [0.3.0](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.2.1...v0.3.0) (2026-06-04)

### 🚀 Features

* **init:** runtime-editable config volume + shipped demo topology ([229db1e](https://github.com/bauer-group/CS-RabbitMQ/commit/229db1ef3ddb6a6e9b7458c683058ee873cdbb12))

## [0.2.1](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.2.0...v0.2.1) (2026-06-03)

### 🐛 Bug Fixes

* **init:** hardened cold-boot readiness; fixed watermark fallback ([63c6bed](https://github.com/bauer-group/CS-RabbitMQ/commit/63c6bedda7e563dc9365b4b629a978ac614dd2bf))

## [0.2.0](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.1.2...v0.2.0) (2026-06-03)

### 🚀 Features

* **rabbitmq-init:** added vhost & user limits provisioning ([60d8881](https://github.com/bauer-group/CS-RabbitMQ/commit/60d88810e9e9ad76ff385c8d511ab1b6ee1c9436))

## [0.1.2](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.1.1...v0.1.2) (2026-06-03)

### ♻️ Refactoring

* **rabbitmq:** streamlined healthcheck to standard retries/interval ([02545f5](https://github.com/bauer-group/CS-RabbitMQ/commit/02545f5fbd2ab4bdeec9a66f37359cc65f7b75c3))

## [0.1.1](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.1.0...v0.1.1) (2026-06-03)

### 🐛 Bug Fixes

* **ci:** stopped monitoring own images in the base-image monitor ([dbf6451](https://github.com/bauer-group/CS-RabbitMQ/commit/dbf645145736582adae3b47521093931eeb72ad6))
* **rabbitmq-init:** actively remove the default guest user ([2e531d0](https://github.com/bauer-group/CS-RabbitMQ/commit/2e531d01fa4a6833229cde60ee29fc691d71035d))
* **rabbitmq:** bounded memory at the application level, not via a hard cap ([e2c617c](https://github.com/bauer-group/CS-RabbitMQ/commit/e2c617c0189070b1d31ba2ffb1076dac03d8057d))

## [0.1.0](https://github.com/bauer-group/CS-RabbitMQ/compare/v0.0.0...v0.1.0) (2026-06-03)

### 🚀 Features

* added modern RabbitMQ 4.3.1 message broker solution ([a9455d0](https://github.com/bauer-group/CS-RabbitMQ/commit/a9455d0e8ac37c9f5d70fb3b0ea5b86b535e776d))

# Changelog

All notable changes to this project are documented here. This file is
maintained automatically by [semantic-release](https://github.com/semantic-release/semantic-release)
based on [Conventional Commits](https://www.conventionalcommits.org/). New
entries are prepended on each release to `main`.

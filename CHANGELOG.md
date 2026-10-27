## [2.0.0b3](https://github.com/betwatch/betwatch-sdk-python/releases/tag/v2.0.0b3) - 2026-10-27

### Features

- Add scoped snapshot and streaming ergonomics ([6fb88e8](https://github.com/betwatch/betwatch-sdk-python/commit/6fb88e87903be708b74797bd6cb882cc2f894840))
- Follow public API contract 2.1.0 ([2820d7e](https://github.com/betwatch/betwatch-sdk-python/commit/2820d7e681f1722703ee14412aa3a065bedf74b1))
- **snapshot**: Keep a card current with EventSnapshot.apply(frame) ([f933510](https://github.com/betwatch/betwatch-sdk-python/commit/f933510041fc2969b0041a2f1bfbac0bf9bf08d0))

### Bug fixes

- **client**: Encode REST filters as CSV ([c0b6e27](https://github.com/betwatch/betwatch-sdk-python/commit/c0b6e27dce6932723d06e051e2e4da7e77c85c5d))
- **ci**: Verify installed SDK version from metadata ([82c7fe0](https://github.com/betwatch/betwatch-sdk-python/commit/82c7fe0ba5706ea8788ed7e31d15f1cf9616e3b1))

### Performance

- **decode**: Decode REST and SSE straight into typed structs ([d00256e](https://github.com/betwatch/betwatch-sdk-python/commit/d00256e82fd36965d45e684a6156b8f20729b5c4))

### Build and CI

- **release**: Generate the changelog and GitHub release from commits ([b562119](https://github.com/betwatch/betwatch-sdk-python/commit/b56211964fecee7953dc8b0b8a891743741537ec))

## [2.0.0b2](https://github.com/betwatch/betwatch-sdk-python/releases/tag/v2.0.0b2) - 2026-08-27

### Features

- Decode snapshot odds_set and drop the AU-only firehose window ([6e3a344](https://github.com/betwatch/betwatch-sdk-python/commit/6e3a34471a2ae060c62352aff4d3a4e355e6bd5a))
- Rewrite the client for the public /v1 REST and SSE API ([8627432](https://github.com/betwatch/betwatch-sdk-python/commit/8627432276ceea4ba52feff88d4273477092da0a))
- Align the client with the final public /v1 contract ([52ce06c](https://github.com/betwatch/betwatch-sdk-python/commit/52ce06ca6fd95af3407df8eda8ef6314123470b1))
- Pin stream recovery and requestId to the final contract ([7c03856](https://github.com/betwatch/betwatch-sdk-python/commit/7c038565ef357fe7274bfe1e41ccead709d01330))
- Move bootstrap progress and change tracking into the SDK ([aafd1fc](https://github.com/betwatch/betwatch-sdk-python/commit/aafd1fc95a07b706e0ada507cc87837f96996131))
- Add a stream-timing tool and track the papercuts log ([52bddc7](https://github.com/betwatch/betwatch-sdk-python/commit/52bddc7e2a8d396229b0b062719a1e34ee9ceade))
- Bootstrap a whole scope over REST instead of waiting for a snapshot ([874b4c2](https://github.com/betwatch/betwatch-sdk-python/commit/874b4c2cbbcd0d676fa32d70655feb3febb6d371))
- Bootstrap any scope with one call, and delete ScopeWatch ([a4125ec](https://github.com/betwatch/betwatch-sdk-python/commit/a4125ec706c7ddc543d952055679c23c436480ef))
- Add a gate runner and a drop-rate mode to the stream timer ([f552b18](https://github.com/betwatch/betwatch-sdk-python/commit/f552b18990fb7b80f7cfcf1a665410507b25da22))
- Target public /v2 and drop market/outcome collections ([1dfea02](https://github.com/betwatch/betwatch-sdk-python/commit/1dfea02af3322f5b4ca2260e5670626b1bc89592))

### Bug fixes

- **examples**: Print live ticks, not the snapshot dump ([dc04cae](https://github.com/betwatch/betwatch-sdk-python/commit/dc04cae2cc0e5d2460d29f8be222cde1c454fe06))
- Stop silently restarting a bootstrap that lost its connection ([ea18b86](https://github.com/betwatch/betwatch-sdk-python/commit/ea18b86c1a3f41412c891204c70c87df473e2723))
- Replay the market, outcome and entrant filters a continuation carries ([87f6a26](https://github.com/betwatch/betwatch-sdk-python/commit/87f6a26179d30f50bc2dccd44a3eaf54a64a4742))
- Measure the path that exists, and use the cursor to attach sooner ([8882c86](https://github.com/betwatch/betwatch-sdk-python/commit/8882c86dff2e47b8d2f33e6ce8b09b3ea33069fc))
- Name an undeclared redirect instead of failing inside the decoder ([751a68c](https://github.com/betwatch/betwatch-sdk-python/commit/751a68c92cb32290a5ee8e0d96d5cd7a1c1633be))
- Follow GET /v2/events/snapshot ([f255019](https://github.com/betwatch/betwatch-sdk-python/commit/f2550197c9588d7bce089ab5f08cde701a8c403b))

### Refactors

- Delete both server compensations ([b432ed4](https://github.com/betwatch/betwatch-sdk-python/commit/b432ed4d888bb71a163b5b39a8451242c854e589))

### Documentation

- State plainly that watch_scope does not bootstrap prices ([b7ae851](https://github.com/betwatch/betwatch-sdk-python/commit/b7ae851f2966a4dd1d3bcdb5f310c2f1a25793fb))
- Mark the two server compensations as temporary ([cb225fb](https://github.com/betwatch/betwatch-sdk-python/commit/cb225fb3a0eff4cf089a22fc44adc6fcab1447e5))
- A 3xx is never Betwatch, and derived ids do not survive a merge ([707b82f](https://github.com/betwatch/betwatch-sdk-python/commit/707b82f587fcf736f19909ca795fd1500a8cf911))

### Build and CI

- Run ruff from the project lockfile in pre-commit ([fdaa3c3](https://github.com/betwatch/betwatch-sdk-python/commit/fdaa3c32d50552d7c15e7540611201ee090e4642))
- Install the wheel into the interpreter the smoke test runs ([fffe386](https://github.com/betwatch/betwatch-sdk-python/commit/fffe38624064fcb0aa611dc90ff2e9c722a171e1))


## v1.7.3 (2026-03-28)

### Fix

- add missing bookmakers

## v1.7.2 (2025-11-25)

## v1.7.1 (2025-11-25)

### Fix

- **deps**: update requirements lock files for CI/CD compatibility

## v1.7.0 (2025-11-25)

### Fix

- **enums**: handle unknown enum values gracefully to prevent crashes

## v1.4.4 (2024-12-05)

## v1.4.3 (2024-12-03)

### Fix

- remove race_id for now pending api updates
- ensure race_id and selection_id is passed through to price updates
- add PremiumBet

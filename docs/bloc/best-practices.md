# Bloc Best Practices

How blocs fit into Synapse's Flutter app.

---

## Bloc or Cubit

| Use a Cubit when | Use a Bloc when |
|------------------|-----------------|
| State changes come from simple method calls | State changes come from a series of events |
| No concurrency rules are needed | You need `restartable`, `droppable`, or `sequential` behaviour |
| Examples: theme, settings level, panel open or closed | Examples: chat, sync jobs, workflow runs, link checking |

Start with a Cubit when in doubt. Converting one to a Bloc later is straightforward.

---

## Layers

```
Widgets  →  Bloc or Cubit  →  Repository  →  Generated engine client
```

**Do**
- Have repositories call the engine client, convert its types to app models, and return `Result<T>`.
- Keep rules about *what to show* in the bloc.
- Keep widgets focused on displaying state and adding events.

**Don't**
- Call the engine client from a bloc or widget.
- Have blocs depend directly on each other. Connect them through a shared repository stream, or through a `BlocListener` in the UI.

```dart
// ❌ Blocs are tightly coupled
class ChatBloc extends Bloc<ChatEvent, ChatState> {
  ChatBloc(this._engineBloc) : super(const ChatState());
  final EngineBloc _engineBloc;
}

// ✅ Both depend on the same stream from a repository
class ChatBloc extends Bloc<ChatEvent, ChatState> {
  ChatBloc({required EngineRepository engine})
      : _engine = engine,
        super(const ChatState()) {
    on<ChatStarted>(_onStarted);
  }

  final EngineRepository _engine;

  Future<void> _onStarted(ChatStarted event, Emitter<ChatState> emit) {
    return emit.forEach<EngineStatus>(
      _engine.status,
      onData: (status) => state.copyWith(engineStatus: status),
    );
  }
}
```

**Why:** Direct bloc dependencies create hidden order problems, and make testing harder.

---

## Providers and scope

**Do**
- Provide repositories at the app level with `MultiRepositoryProvider`, and use its `dispose` callback for cleanup.
- Create a bloc with `BlocProvider(create: ...)` at the screen that owns it. It closes automatically.
- Use `BlocProvider.value` to pass an existing bloc to a new route. It does not close the bloc.
- Keep global blocs to engine status and active jobs.

**Don't**
- Create a bloc with `BlocProvider.value(value: MyBloc())`, because nothing would close it.
- Make every bloc global "just in case".

---

## Reading state in widgets

| API | Use it | Avoid |
|-----|--------|-------|
| `context.read<T>()` | In callbacks, to add events | In `build` to get state, because it won't rebuild |
| `context.watch<T>()` | Inside `build`, in small widgets | At the root of a large `build` |
| `context.select` | Inside `build`, for one value | At the root of a large `build` |
| `BlocBuilder` | To rebuild part of a screen | Side effects: the builder may run many times |
| `BlocListener` | Navigation, snack bars, dialogs | Building UI |
| `BlocConsumer` | Only when you need both | When one of them is enough |

```dart
// ❌ Side effect in a builder, which can run many times
BlocBuilder<SyncBloc, SyncState>(
  builder: (context, state) {
    if (state is SyncFailure) showErrorDialog(context, state.failure);
    return const SyncView();
  },
);

// ✅
BlocListener<SyncBloc, SyncState>(
  listener: (context, state) {
    if (state is SyncFailure) showErrorDialog(context, state.failure);
  },
  child: const SyncView(),
);
```

---

## Errors

**Do**
- Have repositories return `Result<T>`, and turn engine errors into typed failures.
- Convert failures into a state that the UI can show, with a plain message and any fix action.
- Let unexpected errors reach `BlocObserver.onError` for logging.

Synapse declares `Result<T>` as a `sealed` class, which is what makes this `switch` exhaustive. The example in [Coding Standards](../flutter/CODING_STANDARDS.md) uses `abstract class`, which would not compile here.

```dart
final result = await _repository.loadCollections();
emit(switch (result) {
  Success(:final data) => CollectionsLoadSuccess(data),
  Failure(:final error) => CollectionsLoadFailure(error),
});
```

**Don't**
- Swallow errors with an empty `catch`, or show raw engine text to users.
- Leave an error in a status-based state after the next attempt starts.

---

## Streams and subscriptions

**Do**
- Prefer `emit.forEach` for streams consumed inside an event handler. It subscribes and emits for you.
- Use `emit.onEach` when the callback adds events or does not emit a state.
- Provide `onError` for streams that can fail.
- If you must hold a `StreamSubscription`, cancel it in `close()`.

```dart
Future<void> _onSyncStarted(SyncStarted event, Emitter<SyncState> emit) async {
  emit(const SyncInProgress(Progress.zero));
  await emit.forEach<SyncProgress>(
    _repository.watchSync(event.jobId),
    onData: (progress) => progress.isDone
        ? SyncSuccess(progress.summary)
        : SyncInProgress(progress),
    onError: (error, _) => SyncFailure(AppFailure.from(error)),
  );
}
```

**Don't**
- Call `emit` after an `await` from inside a separate callback or `listen`, because the handler may have finished. Use `emit.forEach`, or add an event.

---

## Testing

**Do**
- Test every bloc with `blocTest`, using fake repositories.
- Test success, failure and concurrency: what happens on a second event while the first runs.
- Test widgets with `MockBloc` from `bloc_test`, to render each state.
- Cover all states. The project's 100% coverage rule applies, excluding generated code.

```dart
blocTest<CollectionsBloc, CollectionsState>(
  'emits failure when the engine is unreachable',
  build: () => CollectionsBloc(
    repository: FakeCollectionsRepository.failing(AppFailure.engineOffline),
  ),
  act: (bloc) => bloc.add(const CollectionsStarted()),
  expect: () => const [
    CollectionsLoadInProgress(),
    CollectionsLoadFailure(AppFailure.engineOffline),
  ],
);
```

For `expect` to compare states this way, states need value equality, such as with `Equatable`.

**Don't**
- Test private methods. Test by adding events and checking states.
- Use real timers in tests. Use `wait` or a fake clock.

---

## Review checklist

- [ ] Cubit is used for simple state, and Bloc for event-driven flows.
- [ ] Blocs depend on repositories, not each other or the engine client.
- [ ] The bloc's owner creates it with `create:`, and `.value` only passes existing blocs.
- [ ] Side effects are only in listeners, and builders stay pure.
- [ ] Failures are typed and shown in plain language.
- [ ] Streams use `emit.forEach` or `emit.onEach`, and any held subscription is cancelled.
- [ ] `blocTest` covers success, failure and concurrent events.

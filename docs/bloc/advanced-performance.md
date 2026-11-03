# Advanced Bloc Performance

For when [Performance](./performance.md) is not enough. Use these only after measuring in profile mode.

---

## Event transformers

Each `on<Event>` handler can declare how overlapping events behave, using `bloc_concurrency`.

| Transformer | Behaviour | Synapse examples |
|-------------|-----------|------------------|
| `concurrent()` | Handles events at the same time | Independent per-item actions |
| `sequential()` | Handles events one at a time, in order | Saving settings, so that the last write wins correctly |
| `droppable()` | Ignores new events while one is running | Pressing Sync or Send twice |
| `restartable()` | Cancels the running handler, and handles the newest | Checking a pasted link, or search-as-you-type |

**Do**
- Choose a transformer for each event that starts asynchronous work, and don't rely on the default.
- Combine `restartable` with a debounce for typing.

```dart
EventTransformer<E> debounceRestartable<E>(Duration duration) {
  return (events, mapper) =>
      restartable<E>().call(events.debounce(duration), mapper);
}

on<SourceLinkChanged>(
  _onSourceLinkChanged,
  transformer: debounceRestartable(const Duration(milliseconds: 300)),
);
```

`debounce` here comes from a package such as `stream_transform`. A cancelled handler should also cancel its request to the engine, so the engine does not continue with work nobody wants.

---

## Streaming answers smoothly

An AI answer can produce many small text pieces each second. Rebuilding on each one is wasteful.

**Do**
- Group pieces and emit at a fixed rate, about 20 to 30 times per second.
- Separate the *streaming message* from *finished messages*, so that only the last bubble rebuilds.
- Scope a `BlocSelector` to the streaming text.

```dart
final class ChatState extends Equatable {
  const ChatState({
    this.finished = const [],
    this.finishedVersion = 0,
    this.streamingText = '',
  });

  final List<ChatMessage> finished;
  final int finishedVersion;
  final String streamingText;

  @override
  List<Object?> get props => [finishedVersion, streamingText];
}
```

```dart
// Only this widget rebuilds while an answer arrives
BlocSelector<ChatBloc, ChatState, String>(
  selector: (state) => state.streamingText,
  builder: (context, text) => StreamingBubble(text),
);
```

Comparing `finishedVersion` avoids a deep comparison of the whole chat on each update. This is a deliberate exception to the rule that `props` lists every field, so every change to `finished`, including feedback or switching chats, must also increase the version.

**Don't**
- Re-parse the whole Markdown answer on every update when answers get long. Parse only the new part where possible.

---

## Throttling progress

Sync jobs can report progress thousands of times.

**Do**
- Throttle in the engine first, so fewer events are sent.
- Throttle again in the repository or bloc, with a stream transform.
- Always deliver the final event, using a throttle that keeps the trailing value.

---

## Keeping large lists fast

Value equality compares every list element, which adds up with large lists on frequent updates.

**Do**
- Keep large lists unchanged between updates, and compare them cheaply using an identity check, a length, or a version number.
- Move changing per-item state, such as progress for each source, to a separate small bloc or a map held by ID.
- Use `BlocSelector` per row, selecting only that row's data.

---

## Heavy work and Isolates

Work in a bloc's handler runs on the UI isolate.

**Do**
- Have the engine do heavy processing, which is what it is for.
- Use `Isolate.run` for large JSON responses, or for Markdown parsing of long answers.
- Pass only what's needed, because data is copied between isolates.

```dart
final records = await Isolate.run(() => parseRecordPage(rawJson));
emit(state.copyWith(records: records));
```

**Don't**
- Parse a large response on the UI isolate, which drops frames.

---

## Diagnosing rebuilds and events

**Do**
- Use a debug-only `BlocObserver` to log events and transitions, and to count states per second.
- Use the DevTools Performance view to find dropped frames and the widgets responsible.

```dart
final class DebugBlocObserver extends BlocObserver {
  @override
  void onTransition(Bloc<dynamic, dynamic> bloc, Transition<dynamic, dynamic> transition) {
    super.onTransition(bloc, transition);
    debugPrint('${bloc.runtimeType}: ${transition.event.runtimeType}');
  }
}
```

The `dynamic` here is required by the `BlocObserver` signature, and is a known exception to the no-`dynamic` rule.

**Don't**
- Log state contents in release builds, because they may hold private document text.

---

## Review checklist

- [ ] Every event that starts async work declares a transformer.
- [ ] Cancelled handlers also cancel their engine requests.
- [ ] Answer text is grouped, and only the streaming bubble rebuilds.
- [ ] Progress is throttled, and the final event is never lost.
- [ ] Large lists avoid deep comparison on frequent updates.
- [ ] Expensive parsing runs in an Isolate.
- [ ] Debug observers don't log private content in release builds.

# Bloc Performance

Bloc is rarely slow by itself. Performance problems usually come from rebuilding too much UI. General Dart rules are in [Dart Performance and Concurrency](../flutter/DART_PERFORMANCE_AND_CONCURRENCY.md).

---

## How to approach performance

**Do**
- Use Flutter DevTools in **profile mode**, on a real desktop build.
- Turn on the *rebuild stats* to see which widgets rebuild, and how often.
- Test with realistic data: a long chat, and thousands of records.

**Don't**
- Judge performance from a debug build.

---

## Rebuild as little as possible

**Do**
- Place `BlocBuilder` as low in the tree as possible.
- Use `buildWhen` to skip rebuilds that do not change what the widget shows.
- Use `BlocSelector` or `context.select` to depend on one value. The selected value must be immutable.
- Use `const` widgets wherever possible.

```dart
// ❌ The whole page rebuilds for each word of an answer
class ChatPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final state = context.watch<ChatBloc>().state;
    return Scaffold(
      appBar: const ChatAppBar(),
      body: MessageList(state.messages),
    );
  }
}

// ✅ Only the status indicator rebuilds when the status changes
BlocSelector<ChatBloc, ChatState, ChatStatus>(
  selector: (state) => state.status,
  builder: (context, status) => StatusIndicator(status),
);
```

**Don't**
- Call `context.watch` or `context.select` at the root of a large `build`.
- Use `buildWhen` to hide a state design problem. If a widget wants only part of a state, consider splitting the state.

---

## Value equality

A bloc does not emit a state equal to its current one, and this avoids needless rebuilds. It only works if states have value equality.

**Do**
- Use `Equatable`, or implement `==` and `hashCode`.
- Include every field in `props`.
- Create new lists when content changes.

```dart
// ❌ The same list object, so the new state looks identical and nothing rebuilds
state.messages.add(message);
emit(state.copyWith(messages: state.messages));

// ✅
emit(state.copyWith(messages: [...state.messages, message]));
```

**Don't**
- Forget a field in `props`, which makes real changes disappear. The one exception is a version number standing in for a large list, as explained in [Keeping large lists fast](./advanced-performance.md#keeping-large-lists-fast).
- Compare very large lists deeply on every state change. See [Keeping large lists fast](./advanced-performance.md#keeping-large-lists-fast).

---

## Lists

**Do**
- Use `ListView.builder` for long lists, such as records and run history.
- Give items stable keys based on IDs.
- Page through data from the engine, adding to the state as the user scrolls.

**Don't**
- Hold an entire collection's records in a bloc. Fetch pages from the engine.

---

## Bloc lifetime

**Do**
- Scope blocs to their screen, so their memory is released on leaving it.
- Keep state small, and store IDs when the full data can be fetched.
- Let `BlocProvider` create blocs lazily, unless one must start early.

**Don't**
- Hold long chat histories or document text in a global bloc.

---

## Review checklist

- [ ] Builders are placed low in the tree, and root-level `watch` is avoided.
- [ ] `buildWhen` or selectors are used where only part of a state matters.
- [ ] States have value equality, and all fields are in `props`.
- [ ] Lists in state are replaced, not mutated.
- [ ] Long lists use `ListView.builder`, stable keys, and paging.
- [ ] Performance was checked in profile mode.

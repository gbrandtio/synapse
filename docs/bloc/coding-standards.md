# Bloc Coding Standards

How Bloc code should look in Synapse. The conventions follow the [official naming guidance](https://bloclibrary.dev/naming-conventions/).

---

## File layout

Each feature has its own folder, and one file per bloc, event set and state set.

```
lib/features/chat/
├─ bloc/
│  ├─ chat_bloc.dart
│  ├─ chat_event.dart
│  └─ chat_state.dart
├─ data/chat_repository.dart
└─ view/chat_page.dart
```

---

## Events

**Do**
- Name events in the past tense, as things that already happened: `Subject` + optional noun + verb.
- Name initial-load events `Subject` + `Started`.
- Use a `sealed` base class, with `final` subclasses.

```dart
sealed class ChatEvent {
  const ChatEvent();
}

final class ChatStarted extends ChatEvent {
  const ChatStarted();
}

final class ChatQuestionSubmitted extends ChatEvent {
  const ChatQuestionSubmitted(this.question);

  final String question;
}
```

**Don't**
- Name events as commands: `SendQuestion`, `LoadChat`, or `DoRefresh`.

---

## States

Use one of the two official styles, and choose based on the data.

**Subclasses:** for states that hold different data. This is the default, because the compiler checks that each case is handled.

```dart
sealed class CollectionsState extends Equatable {
  const CollectionsState();

  @override
  List<Object?> get props => const [];
}

final class CollectionsInitial extends CollectionsState {
  const CollectionsInitial();
}

final class CollectionsLoadInProgress extends CollectionsState {
  const CollectionsLoadInProgress();
}

final class CollectionsLoadSuccess extends CollectionsState {
  const CollectionsLoadSuccess(this.collections);

  final List<Collection> collections;

  @override
  List<Object?> get props => [collections];
}

final class CollectionsLoadFailure extends CollectionsState {
  const CollectionsLoadFailure(this.failure);

  final AppFailure failure;

  @override
  List<Object?> get props => [failure];
}
```

**One class with a status:** when data must stay visible across states, such as a chat history that stays on screen during loading. Provide a `copyWith`.

```dart
enum ChatStatus { initial, streaming, success, failure }

final class ChatState extends Equatable {
  const ChatState({
    this.status = ChatStatus.initial,
    this.messages = const [],
    this.failure,
  });

  final ChatStatus status;
  final List<ChatMessage> messages;
  final AppFailure? failure;

  @override
  List<Object?> get props => [status, messages, failure];

  ChatState copyWith({
    ChatStatus? status,
    List<ChatMessage>? messages,
    AppFailure? failure,
  }) =>
      ChatState(
        status: status ?? this.status,
        messages: messages ?? this.messages,
        failure: failure,
      );
}
```

**Do**
- Use `Initial`, `InProgress`, `Success` and `Failure` in state names.
- Keep state immutable, with `final` fields and `const` constructors.
- Use exhaustive `switch` on sealed states, with no `default`.

```dart
// ❌ A new state compiles without being handled
if (state is CollectionsLoadSuccess) { /* ... */ }

// ✅ The compiler fails until every state is handled
return switch (state) {
  CollectionsInitial() || CollectionsLoadInProgress() => const LoadingView(),
  CollectionsLoadSuccess(:final collections) => CollectionList(collections),
  CollectionsLoadFailure(:final failure) => ErrorView(failure),
};
```

**Don't**
- Mutate a list held in state, then emit it. Create a new list instead.
- Name states `Loading`, `Loaded`, or `Failed`.

---

## Blocs and Cubits

**Do**
- Name them `<Feature>Bloc` and `<Feature>Cubit`.
- Pass repositories through the constructor.
- Register all handlers in the constructor, with one `on<Event>` per event, each calling a private method.

```dart
class ChatBloc extends Bloc<ChatEvent, ChatState> {
  ChatBloc({required ChatRepository repository})
      : _repository = repository,
        super(const ChatState()) {
    on<ChatQuestionSubmitted>(_onQuestionSubmitted, transformer: droppable());
  }

  final ChatRepository _repository;

  Future<void> _onQuestionSubmitted(
    ChatQuestionSubmitted event,
    Emitter<ChatState> emit,
  ) async {
    // ...
  }
}
```

**Don't**
- Add public methods to a `Bloc`. Its only input is events.
- Reference `BuildContext` or any widget in a bloc.
- Use `dynamic`, as the Flutter standards forbid it.

---

## Review checklist

- [ ] Event and state names follow the conventions.
- [ ] Events and states are sealed, final and immutable.
- [ ] UI uses exhaustive `switch`, with no `default`.
- [ ] Lists in state are replaced rather than mutated.
- [ ] Blocs have no public methods besides `add`, and no Flutter imports beyond what is needed.

import 'package:bloc_concurrency/bloc_concurrency.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../engine/engine_client.dart';
import '../engine/models.dart';

const _somethingWentWrong = 'Something went wrong. Please try again.';

/// One exchange in the chat.
final class ChatExchange extends Equatable {
  /// Creates an exchange.
  const ChatExchange({
    required this.question,
    this.answer = '',
    this.citations = const [],
    this.problem,
  });

  /// What the user asked.
  final String question;

  /// The answer so far.
  final String answer;

  /// The sources for the answer.
  final List<Citation> citations;

  /// Why there is no answer, if something went wrong.
  final String? problem;

  /// Returns a copy with the given parts changed.
  ChatExchange copyWith({
    String? answer,
    List<Citation>? citations,
    String? problem,
  }) => ChatExchange(
    question: question,
    answer: answer ?? this.answer,
    citations: citations ?? this.citations,
    problem: problem ?? this.problem,
  );

  @override
  List<Object?> get props => [question, answer, citations, problem];
}

/// The chat's contents.
final class ChatState extends Equatable {
  /// Creates the state.
  const ChatState({this.exchanges = const [], this.isAnswering = false});

  /// Every exchange, oldest first.
  final List<ChatExchange> exchanges;

  /// Whether an answer is being written.
  final bool isAnswering;

  @override
  List<Object?> get props => [exchanges, isAnswering];
}

/// The user asked a question.
final class ChatQuestionAsked {
  /// Creates the event.
  const ChatQuestionAsked(this.question);

  /// The question.
  final String question;
}

/// Streams answers into the chat.
final class ChatBloc extends Bloc<ChatQuestionAsked, ChatState> {
  /// Creates the bloc.
  ChatBloc(this._client) : super(const ChatState()) {
    // Droppable, so that pressing Send twice asks once.
    on<ChatQuestionAsked>(_onAsked, transformer: droppable());
  }

  final EngineClient _client;

  Future<void> _onAsked(
    ChatQuestionAsked event,
    Emitter<ChatState> emit,
  ) async {
    final question = event.question.trim();
    if (question.isEmpty) {
      return;
    }
    emit(
      ChatState(
        exchanges: [
          ...state.exchanges,
          ChatExchange(question: question),
        ],
        isAnswering: true,
      ),
    );
    await emit.forEach<AnswerUpdate>(
      _client.ask(question),
      onData: (update) => ChatState(
        exchanges: [
          ...state.exchanges.take(state.exchanges.length - 1),
          _apply(state.exchanges.last, update),
        ],
        isAnswering: true,
      ),
      onError: (_, _) => ChatState(
        exchanges: [
          ...state.exchanges.take(state.exchanges.length - 1),
          state.exchanges.last.copyWith(problem: _somethingWentWrong),
        ],
        isAnswering: true,
      ),
    );
    emit(ChatState(exchanges: state.exchanges));
  }

  ChatExchange _apply(ChatExchange exchange, AnswerUpdate update) {
    return switch (update) {
      AnswerToken(:final text) => exchange.copyWith(
        answer: exchange.answer + text,
      ),
      AnswerCitations(:final citations) => exchange.copyWith(
        citations: citations,
      ),
      AnswerNotFound(:final message) => exchange.copyWith(answer: message),
      AnswerFailed(:final message) => exchange.copyWith(problem: message),
    };
  }
}

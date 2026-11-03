import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synapse_desktop/chat/chat_bloc.dart';
import 'package:synapse_desktop/engine/models.dart';

import 'fake_engine.dart';

void main() {
  var asked = 0;
  const citation = Citation(
    number: 1,
    documentName: 'a.pdf',
    page: 2,
    text: 'x',
    isInferred: false,
  );

  blocTest<ChatBloc, ChatState>(
    'streams tokens, then shows sources',
    build: () => ChatBloc(
      fakeClient({
        '/ask': sse([
          ('token', {'text': 'Fourteen '}),
          ('token', {'text': 'days [1].'}),
          (
            'citations',
            {
              'citations': [
                {
                  'number': 1,
                  'document_name': 'a.pdf',
                  'page': 2,
                  'text': 'x',
                  'is_inferred': false,
                },
              ],
            },
          ),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const ChatQuestionAsked(' How long? ')),
    expect: () => const [
      ChatState(
        exchanges: [ChatExchange(question: 'How long?')],
        isAnswering: true,
      ),
      ChatState(
        exchanges: [ChatExchange(question: 'How long?', answer: 'Fourteen ')],
        isAnswering: true,
      ),
      ChatState(
        exchanges: [
          ChatExchange(question: 'How long?', answer: 'Fourteen days [1].'),
        ],
        isAnswering: true,
      ),
      ChatState(
        exchanges: [
          ChatExchange(
            question: 'How long?',
            answer: 'Fourteen days [1].',
            citations: [citation],
          ),
        ],
        isAnswering: true,
      ),
      ChatState(
        exchanges: [
          ChatExchange(
            question: 'How long?',
            answer: 'Fourteen days [1].',
            citations: [citation],
          ),
        ],
      ),
    ],
  );

  blocTest<ChatBloc, ChatState>(
    'shows the not-found message as the answer',
    build: () => ChatBloc(
      fakeClient({
        '/ask': sse([
          ('not_found', {'message': 'Not found.'}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const ChatQuestionAsked('x')),
    verify: (bloc) {
      expect(bloc.state.exchanges.single.answer, 'Not found.');
      expect(bloc.state.isAnswering, isFalse);
    },
  );

  blocTest<ChatBloc, ChatState>(
    'shows a problem when the engine reports one',
    build: () => ChatBloc(
      fakeClient({
        '/ask': sse([
          ('error', {'message': 'The local AI is missing.'}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const ChatQuestionAsked('x')),
    verify: (bloc) {
      expect(bloc.state.exchanges.single.problem, 'The local AI is missing.');
    },
  );

  blocTest<ChatBloc, ChatState>(
    'shows a problem when the engine cannot be reached',
    build: () => ChatBloc(fakeClient({})),
    act: (bloc) => bloc.add(const ChatQuestionAsked('x')),
    verify: (bloc) {
      expect(bloc.state.exchanges.single.problem, contains('could not reach'));
      expect(bloc.state.isAnswering, isFalse);
    },
  );

  blocTest<ChatBloc, ChatState>(
    'ignores an empty question',
    build: () => ChatBloc(fakeClient({})),
    act: (bloc) => bloc.add(const ChatQuestionAsked('   ')),
    expect: () => const <ChatState>[],
  );

  blocTest<ChatBloc, ChatState>(
    'asks once when Send is pressed twice',
    setUp: () => asked = 0,
    build: () => ChatBloc(
      queuedClient(() {
        asked++;
        return sse([
          ('token', {'text': 'A'}),
        ]);
      }),
    ),
    act: (bloc) => bloc
      ..add(const ChatQuestionAsked('one'))
      ..add(const ChatQuestionAsked('two')),
    verify: (bloc) {
      expect(bloc.state.exchanges.single.question, 'one');
      expect(asked, 1);
    },
  );

  blocTest<ChatBloc, ChatState>(
    'an unexpected reply shape shows a plain problem',
    build: () => ChatBloc(
      fakeClient({
        '/ask': sse([
          ('token', {'wrong': 'shape'}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const ChatQuestionAsked('x')),
    verify: (bloc) {
      expect(bloc.state.exchanges.single.problem, contains('went wrong'));
      expect(bloc.state.isAnswering, isFalse);
    },
  );
}

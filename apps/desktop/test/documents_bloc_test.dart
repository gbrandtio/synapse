import 'dart:convert';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:synapse_desktop/core/result.dart';
import 'package:synapse_desktop/documents/documents_bloc.dart';
import 'package:synapse_desktop/engine/engine_client.dart';
import 'package:synapse_desktop/engine/models.dart';

import 'fake_engine.dart';

void main() {
  const documentJson = {'id': 1, 'name': 'a.pdf', 'pages': 2, 'passages': 3};
  const document = DocumentInfo(id: 1, name: 'a.pdf', pages: 2, passages: 3);

  blocTest<DocumentsBloc, DocumentsState>(
    'loads stored documents',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': http.Response(jsonEncode([documentJson]), 200),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsLoaded()),
    expect: () => const [
      DocumentsState(documents: [document]),
    ],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'reports a load failure',
    build: () => DocumentsBloc(fakeClient({})),
    act: (bloc) => bloc.add(const DocumentsLoaded()),
    verify: (bloc) => expect(bloc.state.error, contains('could not reach')),
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'shows progress, then adds the document',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': sse([
          ('progress', {'message': 'Reading a.pdf', 'done': 0, 'total': 0}),
          ('progress', {'message': 'Processing a.pdf', 'done': 1, 'total': 3}),
          ('finished', {'document': documentJson, 'already_present': false}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    expect: () => const [
      DocumentsState(progress: 'Reading a.pdf'),
      DocumentsState(progress: 'Processing a.pdf: 1 of 3 passages'),
      DocumentsState(documents: [document]),
    ],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'says so when the same file is added twice',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': sse([
          ('finished', {'document': documentJson, 'already_present': true}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    expect: () => const [
      DocumentsState(error: 'a.pdf is already in your documents.'),
    ],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'shows the reason when a file cannot be read',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': sse([
          ('error', {'message': 'bad.pdf could not be read.'}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/bad.pdf'])),
    expect: () => const [DocumentsState(error: 'bad.pdf could not be read.')],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    "keeps one file's problem visible while the next file is added",
    build: () {
      var calls = 0;
      return DocumentsBloc(
        queuedClient(() {
          calls++;
          return calls == 1
              ? sse([
                  ('error', {'message': 'bad.pdf could not be read.'}),
                ])
              : sse([
                  ('progress', {'message': 'Reading', 'done': 0, 'total': 0}),
                  (
                    'finished',
                    {'document': documentJson, 'already_present': false},
                  ),
                ]);
        }),
      );
    },
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/bad.pdf', '/x/a.pdf'])),
    expect: () => const [
      DocumentsState(error: 'bad.pdf could not be read.'),
      DocumentsState(progress: 'Reading', error: 'bad.pdf could not be read.'),
      DocumentsState(
        documents: [document],
        error: 'bad.pdf could not be read.',
      ),
    ],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'a new drop clears the old problem',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': sse([
          ('finished', {'document': documentJson, 'already_present': false}),
        ]),
      }),
    ),
    seed: () => const DocumentsState(error: 'old'),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    expect: () => const [
      DocumentsState(),
      DocumentsState(documents: [document]),
    ],
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'a broken engine reply becomes a plain problem',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': http.Response('event: finished\ndata: {nope}\n\n', 200),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    verify: (bloc) => expect(bloc.state.error, isNotNull),
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'an unexpected reply shape becomes a plain problem',
    build: () => DocumentsBloc(
      fakeClient({
        '/documents': sse([
          ('progress', {'wrong': 'shape'}),
        ]),
      }),
    ),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    verify: (bloc) =>
        expect(bloc.state.error, contains('Something went wrong')),
  );

  blocTest<DocumentsBloc, DocumentsState>(
    'an unreachable engine becomes a plain problem',
    build: () => DocumentsBloc(fakeClient({})),
    act: (bloc) => bloc.add(const DocumentsDropped(['/x/a.pdf'])),
    verify: (bloc) => expect(bloc.state.error, contains('could not reach')),
  );

  test('an error status from the engine is reported', () async {
    final client = fakeClient({'/documents': http.Response('', 500)});
    expect(await client.listDocuments(), isA<Failure<List<DocumentInfo>>>());
  });

  test('the real client can be created', () {
    final client = EngineClient(
      baseUrl: Uri.parse('http://127.0.0.1:1'),
      token: 't',
    );
    expect(client.baseUrl.port, 1);
  });
}

import 'dart:convert';

import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

import '../core/result.dart';
import 'models.dart';
import 'sse.dart';

const _unreachable = 'Synapse could not reach its engine. Please try again.';

/// Talks to the local engine. Everything returned is safe to show the user.
class EngineClient {
  /// Creates a client for the engine at [baseUrl], using the launch [token].
  EngineClient({
    required this.baseUrl,
    required String token,
    http.Client? httpClient,
  }) : _headers = {
         'Authorization': 'Bearer $token',
         'Content-Type': 'application/json',
       },
       _http = httpClient ?? _directClient();

  /// Where the engine is listening.
  final Uri baseUrl;

  // The engine is on this computer, so a proxy set in the environment must
  // never see the token, questions or file paths.
  static http.Client _directClient() =>
      IOClient(HttpClient()..findProxy = (_) => 'DIRECT');
  final Map<String, String> _headers;
  final http.Client _http;

  /// Returns the stored documents.
  Future<Result<List<DocumentInfo>>> listDocuments() async {
    try {
      final response = await _http.get(
        baseUrl.resolve('/documents'),
        headers: _headers,
      );
      if (response.statusCode != 200) {
        return const Failure(_unreachable);
      }
      final rows = jsonDecode(response.body) as List<Object?>;
      return Success([
        for (final row in rows)
          DocumentInfo.fromJson(row! as Map<String, Object?>),
      ]);
    } on http.ClientException {
      return const Failure(_unreachable);
    }
  }

  /// Adds the file at [path], reporting each step.
  Stream<IngestUpdate> addDocument(String path) async* {
    await for (final event in _post('/documents', {'path': path})) {
      switch (event) {
        case Failure<SseEvent>(:final message):
          yield IngestFailed(message);
        case Success<SseEvent>(value: final sse):
          if (sse.name == 'progress') {
            yield IngestProgress(
              sse.data['message']! as String,
              sse.data['done']! as int,
              sse.data['total']! as int,
            );
          } else if (sse.name == 'finished') {
            yield IngestFinished(
              DocumentInfo.fromJson(
                sse.data['document']! as Map<String, Object?>,
              ),
              alreadyPresent: sse.data['already_present']! as bool,
            );
          } else if (sse.name == 'error') {
            yield IngestFailed(sse.data['message']! as String);
          }
      }
    }
  }

  /// Asks [question], streaming the answer.
  Stream<AnswerUpdate> ask(String question) async* {
    await for (final event in _post('/ask', {'question': question})) {
      switch (event) {
        case Failure<SseEvent>(:final message):
          yield AnswerFailed(message);
        case Success<SseEvent>(value: final sse):
          switch (sse.name) {
            case 'token':
              yield AnswerToken(sse.data['text']! as String);
            case 'citations':
              final rows = sse.data['citations']! as List<Object?>;
              yield AnswerCitations([
                for (final row in rows)
                  Citation.fromJson(row! as Map<String, Object?>),
              ]);
            case 'not_found':
              yield AnswerNotFound(sse.data['message']! as String);
            case 'error':
              yield AnswerFailed(sse.data['message']! as String);
          }
      }
    }
  }

  Stream<Result<SseEvent>> _post(String path, Map<String, String> body) async* {
    final request = http.Request('POST', baseUrl.resolve(path))
      ..headers.addAll(_headers)
      ..body = jsonEncode(body);
    try {
      final response = await _http.send(request);
      if (response.statusCode != 200) {
        yield const Failure(_unreachable);
        return;
      }
      await for (final event in parseSse(response.stream)) {
        yield Success(event);
      }
    } on http.ClientException {
      yield const Failure(_unreachable);
    } on FormatException {
      yield const Failure(_unreachable);
    }
  }
}

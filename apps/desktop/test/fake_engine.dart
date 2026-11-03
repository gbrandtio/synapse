import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:synapse_desktop/engine/engine_client.dart';

/// Builds a client whose engine replies with these fixed bodies, by path.
EngineClient fakeClient(Map<String, http.Response> responses) {
  return EngineClient(
    baseUrl: Uri.parse('http://127.0.0.1:1'),
    token: 'test',
    httpClient: MockClient((request) async {
      if (request.headers['Authorization'] != 'Bearer test') {
        return http.Response('', 401);
      }
      final response = responses[request.url.path];
      if (response == null) {
        throw http.ClientException('connection refused');
      }
      return response;
    }),
  );
}

/// Builds a client whose engine computes each reply when asked.
EngineClient queuedClient(http.Response Function() next) {
  return EngineClient(
    baseUrl: Uri.parse('http://127.0.0.1:1'),
    token: 'test',
    httpClient: MockClient((_) async => next()),
  );
}

/// Formats events the way the engine sends them.
http.Response sse(List<(String, Map<String, Object?>)> events) {
  final body = StringBuffer();
  for (final (name, data) in events) {
    body.write('event: $name\ndata: ${jsonEncode(data)}\n\n');
  }
  return http.Response.bytes(utf8.encode(body.toString()), 200);
}

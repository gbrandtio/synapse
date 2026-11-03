import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:synapse_desktop/engine/sse.dart';

void main() {
  Stream<List<int>> bytes(List<String> parts) =>
      Stream.fromIterable(parts.map(utf8.encode));

  test('reads named events, including across chunk boundaries', () async {
    final events = await parseSse(
      bytes(['event: token\r\nda', 'ta: {"text":"hi"}\r\n\r\n']),
    ).toList();
    expect(events.single.name, 'token');
    expect(events.single.data['text'], 'hi');
  });

  test('skips keep-alive comments and nameless events', () async {
    final events = await parseSse(
      bytes([': ping\n\n', 'data: {"a":1}\n\n', 'event: x\ndata: {}\n\n']),
    ).toList();
    expect(events.map((e) => e.name), ['x']);
  });

  test('keeps non-English text intact when split inside a character', () async {
    final encoded = utf8.encode('event: t\ndata: {"text":"é"}\n\n');
    final split = encoded.length - 5; // Between the two bytes of the é.
    final events = await parseSse(
      Stream.fromIterable([encoded.sublist(0, split), encoded.sublist(split)]),
    ).toList();
    expect(events.single.data['text'], 'é');
  });
}

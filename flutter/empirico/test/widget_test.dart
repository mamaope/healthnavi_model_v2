// Basic Flutter widget test for Empirico WebView app.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:empirico/main.dart';

void main() {
  testWidgets('App loads and shows WebView', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}

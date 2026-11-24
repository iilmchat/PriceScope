import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/config.dart';

void main() {
  // Адрес API задаётся при сборке:
  // flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8765
  AppConfig.init();
  runApp(const ProviderScope(child: PriceScopeApp()));
}

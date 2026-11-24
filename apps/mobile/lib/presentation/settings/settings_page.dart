import 'package:flutter/material.dart';

import '../../core/config.dart';

/// Настройки подключения к API (информационный экран v0.1).
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Настройки')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Адрес API', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            SelectableText(AppConfig.apiBaseUrl),
            const SizedBox(height: 16),
            const Text(
              'Адрес задаётся при сборке через --dart-define=API_BASE_URL=… '
              'Для телефона в той же сети укажите IP компьютера с запущенным '
              'pricescope serve --local --host 0.0.0.0.',
            ),
          ],
        ),
      ),
    );
  }
}

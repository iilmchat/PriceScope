import 'package:flutter/material.dart';

import 'core/router.dart';

/// Корневой виджет приложения.
class PriceScopeApp extends StatelessWidget {
  const PriceScopeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'PriceScope',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF3457D5)),
        useMaterial3: true,
      ),
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}

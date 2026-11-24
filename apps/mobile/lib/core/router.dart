import 'package:go_router/go_router.dart';

import '../presentation/compare/compare_page.dart';
import '../presentation/search/search_page.dart';
import '../presentation/settings/settings_page.dart';

/// Маршруты приложения (один код для web и Android).
final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (context, state) => const SearchPage()),
    GoRoute(
      path: '/compare/:productId',
      builder: (context, state) => ComparePage(
        productId: int.tryParse(state.pathParameters['productId'] ?? '') ?? 0,
      ),
    ),
    GoRoute(path: '/settings', builder: (context, state) => const SettingsPage()),
  ],
);

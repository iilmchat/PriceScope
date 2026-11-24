import 'package:go_router/go_router.dart';

import '../presentation/compare/compare_page.dart';
import '../presentation/favorites/favorites_page.dart';
import '../presentation/product/product_page.dart';
import '../presentation/search/search_page.dart';
import '../presentation/settings/settings_page.dart';

/// Маршруты приложения (один код для web и Android).
final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (context, state) => const SearchPage()),
    GoRoute(
      path: '/product/:productId',
      builder: (context, state) => ProductPage(
        productId: int.tryParse(state.pathParameters['productId'] ?? '') ?? 0,
      ),
    ),
    GoRoute(
      path: '/compare',
      builder: (context, state) => ComparePage(
        initialQuery: state.uri.queryParameters['query'] ?? '',
      ),
    ),
    GoRoute(path: '/favorites', builder: (context, state) => const FavoritesPage()),
    GoRoute(path: '/settings', builder: (context, state) => const SettingsPage()),
  ],
);

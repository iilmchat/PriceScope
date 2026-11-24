import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api_client.dart';
import '../data/catalog_repository_impl.dart';
import '../data/favorites_repository_impl.dart';
import '../domain/entities.dart';
import '../domain/repositories.dart';
import '../domain/usecases.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final sharedPreferencesProvider = FutureProvider<SharedPreferences>((ref) async {
  return SharedPreferences.getInstance();
});

final catalogRepositoryProvider = Provider<CatalogRepository>((ref) {
  return CatalogRepositoryImpl(ref.read(apiClientProvider));
});

final favoritesRepositoryProvider = FutureProvider<FavoritesRepository>((ref) async {
  final prefs = await ref.read(sharedPreferencesProvider.future);
  return FavoritesRepositoryImpl(prefs);
});

final searchProductsProvider = Provider<SearchProducts>((ref) {
  return SearchProducts(ref.read(catalogRepositoryProvider));
});

final getPriceHistoryProvider = Provider<GetPriceHistory>((ref) {
  return GetPriceHistory(ref.read(catalogRepositoryProvider));
});

final comparePricesProvider = Provider<ComparePrices>((ref) {
  return ComparePrices(ref.read(catalogRepositoryProvider));
});

final manageFavoritesProvider = FutureProvider<ManageFavorites>((ref) async {
  final repository = await ref.read(favoritesRepositoryProvider.future);
  return ManageFavorites(repository);
});

final searchQueryProvider = StateProvider<String>((ref) => '');

final compareResultsProvider = FutureProvider.family<List<PriceComparison>, String>((ref, query) {
  if (query.trim().isEmpty) return Future.value(const <PriceComparison>[]);
  return ref.read(comparePricesProvider)(query.trim());
});

final getProductDetailsProvider = Provider<GetProductDetails>((ref) {
  return GetProductDetails(ref.read(catalogRepositoryProvider));
});

final productProvider = FutureProvider.family<Product?, int>((ref, id) {
  return ref.read(getProductDetailsProvider)(id);
});

final historyProvider = FutureProvider.family<List<PricePoint>, int>((ref, productId) {
  return ref.read(getPriceHistoryProvider)(productId);
});

final productsProvider = FutureProvider.family<List<Product>, String>((ref, query) {
  if (query.trim().isEmpty) return Future.value(const <Product>[]);
  return ref.read(searchProductsProvider)(query.trim());
});

final favoritesProvider = FutureProvider<List<Favorite>>((ref) async {
  final repository = await ref.read(favoritesRepositoryProvider.future);
  return repository.load();
});

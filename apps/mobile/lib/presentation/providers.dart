import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../data/models/product.dart';
import '../data/repositories.dart';
import '../domain/repositories.dart';

final catalogRepositoryProvider = Provider<CatalogRepository>(
  (ref) => CatalogRepositoryImpl(ref.read(apiClientProvider)),
);

final searchQueryProvider = StateProvider<String>((ref) => '');

final productsProvider = FutureProvider.family<List<ProductDto>, String>((ref, query) async {
  return ref.read(catalogRepositoryProvider).search(query);
});

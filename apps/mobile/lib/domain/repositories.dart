import '../data/models/product.dart';

/// Абстракция репозитория каталога (domain не знает про Dio).
abstract class CatalogRepository {
  Future<List<ProductDto>> search(String query);
  Future<List<CompareRowDto>> compare(int productId);
}

import '../domain/entities.dart';

/// Разбор ответов REST API в доменные сущности.

Product parseProduct(Map<String, dynamic> json) {
  final images = (json['image_urls'] as List?)?.cast<String>() ?? const <String>[];
  return Product(
    id: (json['id'] as num).toInt(),
    name: json['canonical_name']?.toString() ?? '',
    brand: json['brand']?.toString(),
    category: json['category_path']?.toString(),
    imageUrl: images.isEmpty ? null : images.first,
  );
}

PricePoint parsePricePoint(Map<String, dynamic> json) {
  return PricePoint(
    observedAt: DateTime.tryParse(json['observed_at']?.toString() ?? '') ?? DateTime.now(),
    priceMinor: (json['price_minor'] as num?)?.toInt() ?? 0,
    storeCode: json['store_code']?.toString() ?? '',
  );
}

PriceComparison parseComparison(Map<String, dynamic> json) {
  return PriceComparison(
    storeCode: json['store_code']?.toString() ?? '',
    priceMinor: (json['price_minor'] as num?)?.toInt() ?? 0,
    observedAt: DateTime.tryParse(json['observed_at']?.toString() ?? '') ?? DateTime.now(),
    isCheapest: json['is_cheapest'] as bool? ?? false,
    savingsPct: (json['savings_pct'] as num?)?.toDouble() ?? 0,
    pricePerLiterMinor: (json['price_per_l_minor'] as num?)?.toInt(),
    pricePerKgMinor: (json['price_per_kg_minor'] as num?)?.toInt(),
  );
}

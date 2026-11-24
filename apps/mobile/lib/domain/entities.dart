/// Доменные сущности клиента (не зависят от API и БД).

class Product {
  const Product({
    required this.id,
    required this.name,
    this.brand,
    this.category,
    this.imageUrl,
  });

  final int id;
  final String name;
  final String? brand;
  final String? category;
  final String? imageUrl;
}

class PricePoint {
  const PricePoint({
    required this.observedAt,
    required this.priceMinor,
    required this.storeCode,
  });

  final DateTime observedAt;
  final int priceMinor;
  final String storeCode;
}

class PriceComparison {
  const PriceComparison({
    required this.storeCode,
    required this.priceMinor,
    required this.observedAt,
    this.isCheapest = false,
    this.savingsPct = 0,
    this.pricePerLiterMinor,
    this.pricePerKgMinor,
  });

  final String storeCode;
  final int priceMinor;
  final DateTime observedAt;
  final bool isCheapest;
  final double savingsPct;
  final int? pricePerLiterMinor;
  final int? pricePerKgMinor;
}

class Favorite {
  const Favorite({
    required this.externalId,
    required this.storeCode,
    required this.name,
    required this.priceMinor,
    this.imageUrl,
  });

  final String externalId;
  final String storeCode;
  final String name;
  final int priceMinor;
  final String? imageUrl;
}

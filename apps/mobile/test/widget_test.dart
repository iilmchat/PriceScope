import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pricescope_mobile/data/api_dto.dart';
import 'package:pricescope_mobile/presentation/widgets/price_badge.dart';

void main() {
  test('разбор DTO товара из ответа API', () {
    final product = parseProduct({
      'id': 42,
      'canonical_name': 'Дезодорант РЕКСОНА 100мл',
      'brand': 'РЕКСОНА',
      'category_path': 'Красота/Дезодоранты',
      'image_urls': ['https://cdn.example.test/42.png'],
    });
    expect(product.id, 42);
    expect(product.name, contains('РЕКСОНА'));
    expect(product.imageUrl, 'https://cdn.example.test/42.png');
  });

  testWidgets('PriceBadge показывает цену в рублях', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: PriceBadge(priceMinor: 19990))),
    );
    final text = tester.widget<Text>(find.byType(Text));
    expect(text.data, contains('199'));
  });
}

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:pricescope_mobile/app.dart';

void main() {
  testWidgets('Приложение отображает экран поиска', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: PriceScopeApp()));
    await tester.pumpAndSettle();
    expect(find.text('PriceScope — поиск'), findsOneWidget);
  });
}

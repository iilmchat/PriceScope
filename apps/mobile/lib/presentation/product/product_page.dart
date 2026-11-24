import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domain/entities.dart';
import '../providers.dart';
import '../widgets/empty_state.dart';
import '../widgets/price_badge.dart';

/// Карточка товара: атрибуты, график истории цен и сравнение.
class ProductPage extends ConsumerWidget {
  const ProductPage({super.key, required this.productId});

  final int productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final product = ref.watch(productProvider(productId));
    final history = ref.watch(historyProvider(productId));

    return Scaffold(
      appBar: AppBar(title: const Text('Карточка товара')),
      body: product.when(
        data: (item) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (item != null) ...[
              if (item.imageUrl != null)
                Image.network(
                  item.imageUrl!,
                  height: 180,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const SizedBox(height: 180),
                ),
              Text(item.name, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(item.brand ?? item.category ?? ''),
              const SizedBox(height: 16),
              FilledButton.icon(
                icon: const Icon(Icons.compare_arrows),
                label: const Text('Сравнить цены'),
                onPressed: () => context.go(
                  '/compare?query=${Uri.encodeComponent(item.name)}',
                ),
              ),
              const SizedBox(height: 24),
            ],
            Text('История цен', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            history.when(
              data: (points) {
                if (points.isEmpty) {
                  return const EmptyState(message: 'История цен пока пуста');
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    SizedBox(height: 180, child: _PriceChart(points: points)),
                    const SizedBox(height: 12),
                    ...points.reversed.map(
                      (point) => ListTile(
                        leading: PriceBadge(priceMinor: point.priceMinor),
                        title: Text(point.storeCode),
                        subtitle: Text(point.observedAt.toLocal().toString()),
                      ),
                    ),
                  ],
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => EmptyState(message: 'Ошибка: $error'),
            ),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => EmptyState(message: 'Ошибка: $error'),
      ),
    );
  }
}

class _PriceChart extends StatelessWidget {
  const _PriceChart({required this.points});

  final List<PricePoint> points;

  @override
  Widget build(BuildContext context) {
    final spots = points
        .asMap()
        .entries
        .map((entry) => FlSpot(entry.key.toDouble(), entry.value.priceMinor / 100))
        .toList();
    return LineChart(
      LineChartData(
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(show: false),
          ),
        ],
        gridData: const FlGridData(show: true),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: true),
      ),
    );
  }
}

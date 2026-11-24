import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Формат цены из копеек в рубли.
String formatPrice(int minor) {
  return NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 2)
      .format(minor / 100);
}

/// Бейдж цены; подсвечивает самое дешёвое предложение.
class PriceBadge extends StatelessWidget {
  const PriceBadge({super.key, required this.priceMinor, this.isCheapest = false});

  final int priceMinor;
  final bool isCheapest;

  @override
  Widget build(BuildContext context) {
    final color = isCheapest ? Colors.green.shade700 : Colors.indigo;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        formatPrice(priceMinor),
        style: TextStyle(color: color, fontWeight: FontWeight.w700),
      ),
    );
  }
}

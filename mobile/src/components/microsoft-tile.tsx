/**
 * The four-square Microsoft mark.
 *
 * Drawn with plain Views rather than an SVG dependency — it is four squares,
 * and this app has no other use for a renderer.
 */

import { StyleSheet, View } from 'react-native';

const SQUARES = ['#f25022', '#7fba00', '#00a4ef', '#ffb900'] as const;

export function MicrosoftTile({ size = 18 }: { size?: number }) {
  const cell = (size - 2) / 2;
  return (
    <View style={[styles.grid, { width: size, height: size }]}>
      {SQUARES.map((color) => (
        <View key={color} style={{ width: cell, height: cell, backgroundColor: color }} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    alignContent: 'space-between',
  },
});

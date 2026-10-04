/**
 * The trajectory mark — the same glyph as the app icon and the web login.
 *
 * A raster rather than an SVG: the tile carries its own colours, and this app
 * has no other use for a renderer.
 */

import { Image } from 'expo-image';
import { StyleSheet, View, type ViewStyle } from 'react-native';

const MARK = require('../../assets/images/brand-mark.png');

interface BrandLogoProps {
  /** Edge length of the square tile. */
  size?: number;
  style?: ViewStyle;
}

export function BrandLogo({ size = 64, style }: BrandLogoProps) {
  return (
    <View style={[styles.wrap, style]}>
      <Image
        source={MARK}
        style={{ width: size, height: size }}
        contentFit="contain"
        accessibilityLabel="BrainVar Trajectory Explorer"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: 'center',
  },
});

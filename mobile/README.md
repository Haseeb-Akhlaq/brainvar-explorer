# BrainVar mobile

Expo app for the BrainVar Trajectory Explorer. **One screen so far — the
login form, and it is presentation only.** There is no auth client, no API
base and no session storage; `onPress` on both buttons is a deliberate no-op
rather than a stub that pretends to sign in.

Stack matches the FSUK Star Portal app: Expo SDK 56, expo-router, React
Native 0.85, React 19, TypeScript 6, Outfit via `@expo-google-fonts/outfit`.

## Running

```bash
npm install
npm start          # then press i / a, or scan the QR code
npm run ios        # needs Xcode
npm run android    # needs Android Studio
npm run web        # quickest look — react-native-web
```

## Layout

```
src/
  app/                 expo-router routes
    _layout.tsx        fonts, splash, Stack
    index.tsx          redirects to /login
    login.tsx          the screen
  components/          brand-* presentational components
  constants/theme.ts   design tokens, mirroring frontend/src/index.css
assets/images/         logo and generated app icons
```

`@/*` maps to `src/*`.

## Notes

- **Dark only.** The web app has a light theme behind a toggle; this ships one
  scheme until there is a reason for the second.
- **`web.output` is `single`, not `static`.** Static output prerenders routes
  in Node, where `requestAnimationFrame` does not exist, and the bundle throws
  on boot. An SPA build is the right shape for this app anyway.
- Icons in `assets/images/` are the same trajectory mark as the web favicon;
  the store icon is opaque brand blue, and the Android adaptive icon is the
  white glyph over that colour.

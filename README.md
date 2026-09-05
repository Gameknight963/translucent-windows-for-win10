## Translucent Windows for Windows 10

Port of [Translucent Windows](https://windhawk.net/mods/translucent-windows) windhawk mod to win10.

The original mod technically already works with Windows 10, but this port has better compatibility and more Windows 10 specific features.

Shown with OpenGlass + aero10.1

![](https://i.imgur.com/Rfe39LW.png)

## Deviations from translucent-windows:
 
1. **Uses Windows 10 Composition Effects** Replaced Windows 11-only DWM backdrop types with Windows 10's `SetWindowCompositionAttribute` +`ACCENT_POLICY`
2. **Aero glass**: Now supports `DwmEnableBlurBehindWindow`, for usage with DWM shaders
3. **Process exclusion simplification** Replaced the original per-process options with a simple flat list. Per-process settings aren't really that useful in the original mod so I opted to remove them to make exclusions easier to configure
4. **Win32 Dialog & Property Sheet Dark Theming** Intercepts `DefDlgProcW` and `EnableThemeDialogTexture` to use `DarkMode_Explorer` and dark background brushes across classic Win32 dialogs and property sheets
5. **Optional Subpixel ClearType Rendering** Added the `ClearTypeText` setting to preserve per-channel RGB subpixel antialiasing on translucent windows instead of converting text to grayscale
6. **Configurable Text Weight / Gamma** Added the `TextGamma` setting (1.0 to 5.0, default 1.4) to allow fine-tuning of font boldness and contrast
7. **Configurable Dark Mode Titlebars**: Added the `DarkModeTitlebars` setting to toggle immersive dark titlebars, with support across all Windows 10 builds (falls back to attribute 19 on builds 1809–1909). Previously this was forced on
8. **Immersive Menu Fix** Fixed immersive context menu fonts being 1pt too large by not overridding `pFont->lfHeight`


## Installation

Copy the contents from [here](https://github.com/Gameknight963/translucent-windows-for-win10/blob/master/translucent-windows-win10.wh.cpp) and put them in a new mod.

I might make a PR to add this to windhawk-mods sometime later, but it's just a paint to do
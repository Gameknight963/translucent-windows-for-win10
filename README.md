WIP port of [Translucent Windows](https://windhawk.net/mods/translucent-windows) windhawk mod to win10.

The mod already technically works with win10, but the compatibility is not good

Shown with OpenGlass + aero10p1

<img width="889" height="542" alt="image" src="https://github.com/user-attachments/assets/3011e826-b7f5-4543-a09f-4eecf52e04ac" />

Changes vs original translucent-windows.wh.cpp:
 
 1. Remove Win11-only SystemBackdrop (Mica/Acrylic via DwmSetWindowAttribute).
 2. DwmExtendFrameIntoClientArea enabled by default (clean frame extension without conflicting blur regions).
 3. In-memory GetSysColor and GetSysColorBrush hooks provide transparent dark brushes per hooked process without calling SetSysColors or modifying the registry.
 4. Remove Process Rules (use Windhawk's built-in process exclusions instead).
 5. Support SetWindowCompositionAttribute (AccentPolicy) modes alongside a dedicated DwmEnableBlurBehindWindow option.
 6. Preserve standard fonts and use standard Segoe UI instead of Windows 11-only Segoe UI Variable.
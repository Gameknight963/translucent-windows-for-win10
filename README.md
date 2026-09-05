WIP port of [Translucent Windows](https://windhawk.net/mods/translucent-windows) windhawk mod to win10.

The mod already technically works with win10, but the compatibility is not good

Shown with OpenGlass + aero10p1

<img width="889" height="542" alt="image" src="https://github.com/user-attachments/assets/3011e826-b7f5-4543-a09f-4eecf52e04ac" />

Changes vs original translucent-windows.wh.cpp:
 
 1.  Remove Win11-only SystemBackdrop (Mica/Acrylic via DwmSetWindowAttribute)
  2.  Make DwmExtendFrameIntoClientArea explicitly opt-in via setting
  3.  Remove SetSysColors and all related infrastructure
  4.  Remove Process Rules (use Windhawk built-in exclusions instead)
  5.  Support 5 ACCENT_STATE values (0-4) via SetWindowCompositionAttribute. 
      extending frame so DwmBlurGlass-style compositors see real glass, not black
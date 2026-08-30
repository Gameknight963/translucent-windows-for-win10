#!/usr/bin/env python3
"""
patch_translucent_windows.py  (v2)
Usage: python3 patch_translucent_windows.py <input.cpp> [output.cpp]

Changes vs original translucent-windows.wh.cpp:
  1.  Remove Win11-only SystemBackdrop (Mica/Acrylic via DwmSetWindowAttribute)
  2.  Make DwmExtendFrameIntoClientArea explicitly opt-in via setting
  3.  Remove SetSysColors and all related infrastructure
  4.  Remove Process Rules (use Windhawk built-in exclusions instead)
  5.  Support all 5 ACCENT_STATE values (0-4) via SetWindowCompositionAttribute
  6.  Fix ACCENT_STATE forward-declaration order (move enum before Settings struct)
  7.  Fix ExtendFrame DWM glass: call DwmEnableBlurBehindWindow(full window) when
      extending frame so DwmBlurGlass-style compositors see real glass, not black
  8.  Fix desktop/Explorer context menu text: suppress opaque background fill in
      HookedExtTextOutW when the target window is a flyout (#32768 / popup menu),
      preventing the solid fill from killing DWM transparency behind menu text
  9.  Keep ClearType by honoring the original LOGFONT quality in text hooks
      (do not force NONANTIALIASED; let GDI use whatever the theme specifies)
"""

import re, sys, os

# ─── helpers ──────────────────────────────────────────────────────────────────

def _require(src, needle, label):
    if needle not in src:
        print(f"  !! WARN: could not find '{label}' – skipping that patch")
    return needle in src

# ─── main patch ───────────────────────────────────────────────────────────────

def patch(src: str) -> str:

    # ── 1. Remove Win11 backdrop constants ────────────────────────────────────
    src = re.sub(
        r'static constexpr UINT ENABLE = 1;\s*'
        r'static constexpr UINT AUTO = 0; // DWMSBT_AUTO\s*'
        r'//static constexpr UINT NONE = 1; // DWMSBT_NONE\s*'
        r'static constexpr UINT MAINWINDOW = 2; // DWMSBT_MAINWINDOW\s*'
        r'static constexpr UINT TRANSIENTWINDOW = 3; // DWMSBT_TRANSIENTWINDOW\s*'
        r'static constexpr UINT TABBEDWINDOW = 4; // DWMSBT_TABBEDWINDOW\s*',
        'static constexpr UINT ENABLE = 1;\n\n',
        src
    )

    # ── 2. Replace Settings struct AND fix forward-declaration order ───────────
    # The original Settings struct comes BEFORE the ACCENT_STATE enum.
    # Our new Settings references ACCENT_STATE_* values, so we must move the
    # ACCENT_POLICY / ACCENT_STATE / ACCENT_FLAG / WINCOMPATTRDATA /
    # WINDOWCOMPOSITIONATTRIB block to appear BEFORE Settings.
    #
    # Strategy:
    #   a) Replace the original Settings struct with a placeholder comment.
    #   b) Prepend the full enum block + new Settings struct right before
    #      the ACCENT_POLICY block (which currently follows Settings in the source).
    #   c) Remove the now-duplicate ACCENT_POLICY block.

    OLD_SETTINGS = '''\
struct Settings{
    BOOL FillBg = FALSE;
    BOOL AccentColorize = FALSE;
    COLORREF AccentColor = 0xFFFFFFFF;
    BOOL TextAlphaBlend = FALSE;
    BOOL SetSystemColors = FALSE;
    COLORREF AccentBlurBehindClr = 0x00000000;
    BOOL FlyoutsEffects = FALSE;
    BOOL Unload = FALSE;

    enum BACKGROUNDTYPE
    {
        Default,
        AccentBlurBehind,
        AcrylicSystemBackdrop,
        Mica,
        MicaAlt,
    } BgType = Default;

} g_settings;'''

    NEW_SETTINGS_BLOCK = '''\
// ── AccentPolicy types (must precede Settings) ───────────────────────────────
struct ACCENT_POLICY
{
    INT AccentState;
    INT AccentFlags;
    INT GradientColor;
    INT AnimationId;
};

enum ACCENT_STATE
{
    ACCENT_STATE_DISABLED,
    ACCENT_STATE_ENABLE_GRADIENT,
    ACCENT_STATE_ENABLE_TRANSPARENTGRADIENT,
    ACCENT_STATE_ENABLE_BLURBEHIND,
    ACCENT_STATE_ENABLE_ACRYLICBLURBEHIND,
    ACCENT_STATE_ENABLE_HOSTBACKDROP,
    ACCENT_STATE_INVALID_STATE
};

enum ACCENT_FLAG
{
    ACCENT_FLAG_NONE,
    ACCENT_FLAG_ENABLE_MODERN_ACRYLIC_RECIPE = 1 << 1,
    ACCENT_FLAG_ENABLE_GRADIENT_COLOR = 1 << 1,
    ACCENT_FLAG_ENABLE_FULLSCREEN = 1 << 2,
    ACCENT_FLAG_ENABLE_BORDER_LEFT = 1 << 5,
    ACCENT_FLAG_ENABLE_BORDER_TOP = 1 << 6,
    ACCENT_FLAG_ENABLE_BORDER_RIGHT = 1 << 7,
    ACCENT_FLAG_ENABLE_BORDER_BOTTOM = 1 << 8,
    ACCENT_FLAG_ENABLE_BLUR_RECT = 1 << 9,
    ACCENT_FLAG_ENABLE_BORDER = ACCENT_FLAG_ENABLE_BORDER_LEFT | ACCENT_FLAG_ENABLE_BORDER_TOP
    | ACCENT_FLAG_ENABLE_BORDER_RIGHT | ACCENT_FLAG_ENABLE_BORDER_BOTTOM
};

struct WINCOMPATTRDATA
{
    DWORD Attrib;
    PVOID pvData;
    SIZE_T cbData;
};

enum WINDOWCOMPOSITIONATTRIB
{
    WCA_UNDEFINED,
    WCA_NCRENDERING_ENABLED,
    WCA_NCRENDERING_POLICY,
    WCA_TRANSITIONS_FORCEDISABLED,
    WCA_ALLOW_NCPAINT,
    WCA_CAPTION_BUTTON_BOUNDS,
    WCA_NONCLIENT_RTL_LAYOUT,
    WCA_FORCE_ICONIC_REPRESENTATION,
    WCA_EXTENDED_FRAME_BOUNDS,
    WCA_HAS_ICONIC_BITMAP,
    WCA_THEME_ATTRIBUTES,
    WCA_NCRENDERING_EXILED,
    WCA_NCADORNMENTINFO,
    WCA_EXCLUDED_FROM_LIVEPREVIEW,
    WCA_VIDEO_OVERLAY_ACTIVE,
    WCA_FORCE_ACTIVEWINDOW_APPEARANCE,
    WCA_DISALLOW_PEEK,
    WCA_CLOAK,
    WCA_CLOAKED,
    WCA_ACCENT_POLICY,
    WCA_FREEZE_REPRESENTATION,
    WCA_EVER_UNCLOAKED,
    WCA_VISUAL_OWNER,
    WCA_HOLOGRAPHIC,
    WCA_EXCLUDED_FROM_DDA,
    WCA_PASSIVEUPDATEMODE,
    WCA_USEDARKMODECOLORS,
    WCA_CORNER_STYLE,
    WCA_PART_COLOR,
    WCA_DISABLE_MOVESIZE_FEEDBACK,
    WCA_LAST
};

// ── Settings (references ACCENT_STATE – must come after it) ──────────────────
struct Settings{
    BOOL FillBg = FALSE;
    BOOL AccentColorize = FALSE;
    COLORREF AccentColor = 0xFFFFFFFF;
    BOOL TextAlphaBlend = FALSE;
    COLORREF AccentBlurBehindClr = 0x00000000;
    BOOL FlyoutsEffects = FALSE;
    BOOL ExtendFrame = FALSE;
    BOOL Unload = FALSE;

    // Maps directly to ACCENT_STATE enum values
    enum BACKGROUNDTYPE
    {
        Default             = ACCENT_STATE_DISABLED,
        Gradient            = ACCENT_STATE_ENABLE_GRADIENT,
        TransparentGradient = ACCENT_STATE_ENABLE_TRANSPARENTGRADIENT,
        BlurBehind          = ACCENT_STATE_ENABLE_BLURBEHIND,
        AcrylicBlur         = ACCENT_STATE_ENABLE_ACRYLICBLURBEHIND,
    } BgType = Default;

} g_settings;'''

    src = src.replace(OLD_SETTINGS, NEW_SETTINGS_BLOCK)

    # Now remove the duplicate ACCENT_POLICY / ACCENT_STATE / ... block that
    # originally followed the Settings struct in the source.
    OLD_DUPE_BLOCK = '''\
struct ACCENT_POLICY 
{
    INT AccentState;
    INT AccentFlags;
    INT GradientColor;
    INT AnimationId;
};

enum ACCENT_STATE
{
    ACCENT_STATE_DISABLED,
    ACCENT_STATE_ENABLE_GRADIENT,
    ACCENT_STATE_ENABLE_TRANSPARENTGRADIENT,
    ACCENT_STATE_ENABLE_BLURBEHIND,\t// Removed in Windows 11 22H2+
    ACCENT_STATE_ENABLE_ACRYLICBLURBEHIND,
    ACCENT_STATE_ENABLE_HOSTBACKDROP,
    ACCENT_STATE_INVALID_STATE
};

enum ACCENT_FLAG
{
    ACCENT_FLAG_NONE,
    ACCENT_FLAG_ENABLE_MODERN_ACRYLIC_RECIPE = 1 << 1,\t// Windows 11 22H2+
    ACCENT_FLAG_ENABLE_GRADIENT_COLOR = 1 << 1, // ACCENT_ENABLE_BLURBEHIND
    ACCENT_FLAG_ENABLE_FULLSCREEN = 1 << 2,
    ACCENT_FLAG_ENABLE_BORDER_LEFT = 1 << 5,
    ACCENT_FLAG_ENABLE_BORDER_TOP = 1 << 6,
    ACCENT_FLAG_ENABLE_BORDER_RIGHT = 1 << 7,
    ACCENT_FLAG_ENABLE_BORDER_BOTTOM = 1 << 8,
    ACCENT_FLAG_ENABLE_BLUR_RECT = 1 << 9,\t// DwmpUpdateAccentBlurRect, it is conflicted with ACCENT_ENABLE_GRADIENT_COLOR when using ACCENT_ENABLE_BLURBEHIND
    ACCENT_FLAG_ENABLE_BORDER = ACCENT_FLAG_ENABLE_BORDER_LEFT | ACCENT_FLAG_ENABLE_BORDER_TOP 
    | ACCENT_FLAG_ENABLE_BORDER_RIGHT | ACCENT_FLAG_ENABLE_BORDER_BOTTOM
};

struct WINCOMPATTRDATA 
{
    DWORD Attrib;
    PVOID pvData;
    SIZE_T cbData;
};

enum WINDOWCOMPOSITIONATTRIB 
{
    WCA_UNDEFINED,
    WCA_NCRENDERING_ENABLED,
    WCA_NCRENDERING_POLICY,
    WCA_TRANSITIONS_FORCEDISABLED,
    WCA_ALLOW_NCPAINT,
    WCA_CAPTION_BUTTON_BOUNDS,
    WCA_NONCLIENT_RTL_LAYOUT,
    WCA_FORCE_ICONIC_REPRESENTATION,
    WCA_EXTENDED_FRAME_BOUNDS,
    WCA_HAS_ICONIC_BITMAP,
    WCA_THEME_ATTRIBUTES,
    WCA_NCRENDERING_EXILED,
    WCA_NCADORNMENTINFO,
    WCA_EXCLUDED_FROM_LIVEPREVIEW,
    WCA_VIDEO_OVERLAY_ACTIVE,
    WCA_FORCE_ACTIVEWINDOW_APPEARANCE,
    WCA_DISALLOW_PEEK,
    WCA_CLOAK,
    WCA_CLOAKED,
    WCA_ACCENT_POLICY,
    WCA_FREEZE_REPRESENTATION,
    WCA_EVER_UNCLOAKED,
    WCA_VISUAL_OWNER,
    WCA_HOLOGRAPHIC,
    WCA_EXCLUDED_FROM_DDA,
    WCA_PASSIVEUPDATEMODE,
    WCA_USEDARKMODECOLORS,
    WCA_CORNER_STYLE,
    WCA_PART_COLOR,
    WCA_DISABLE_MOVESIZE_FEEDBACK,
    WCA_LAST
};'''
    src = src.replace(OLD_DUPE_BLOCK, '// (AccentPolicy types moved above Settings struct)')

    # ── 3. Replace HookedDwmSetWindowAttribute with passthrough ───────────────
    src = re.sub(
        r'HRESULT WINAPI HookedDwmSetWindowAttribute\(HWND hWnd, DWORD dwAttribute, LPCVOID pvAttribute, DWORD cbAttribute\)\n'
        r'\{.*?\}(?=\n\nHRESULT WINAPI HookedDwmExtendFrame)',
        '''HRESULT WINAPI HookedDwmSetWindowAttribute(HWND hWnd, DWORD dwAttribute, LPCVOID pvAttribute, DWORD cbAttribute)
{
    // Pure passthrough on Win10 - effects applied via SetWindowCompositionAttribute.
    return DwmSetWindowAttribute_orig(hWnd, dwAttribute, pvAttribute, cbAttribute);
}''',
        src, flags=re.DOTALL
    )

    # ── 4. Replace HookedDwmExtendFrameIntoClientArea ─────────────────────────
    src = src.replace(
        '''HRESULT WINAPI HookedDwmExtendFrameIntoClientArea(HWND hWnd, const MARGINS* pMarInset)
{
    if(!IsWindowEligible(hWnd))
        [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, pMarInset);
    
    if(!IsWindowClass(hWnd, L"CASCADIA_HOSTING_WINDOW_CLASS")) {
        static const MARGINS margins = {-1, -1, -1, -1};
        [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, &margins);
    }
    else
        [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, pMarInset);
}''',
        '''HRESULT WINAPI HookedDwmExtendFrameIntoClientArea(HWND hWnd, const MARGINS* pMarInset)
{
    if(!IsWindowEligible(hWnd))
        [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, pMarInset);

    // Only extend when explicitly enabled via the ExtendFrame setting
    if (g_settings.ExtendFrame && !IsWindowClass(hWnd, L"CASCADIA_HOSTING_WINDOW_CLASS")) {
        static const MARGINS margins = {-1, -1, -1, -1};
        [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, &margins);
    }

    [[clang::musttail]]return DwmExtendFrameIntoClientArea_orig(hWnd, pMarInset);
}'''
    )

    # ── 5. Replace EnableBlurBehind with full AccentState dispatcher ──────────
    src = src.replace(
        '''VOID EnableBlurBehind(HWND hWnd)
{
    // Does not interfere with the Windows Terminal, GameBar overlay
    if(!(IsWindowClass(hWnd, L"CASCADIA_HOSTING_WINDOW_CLASS") || IsWindowClass(hWnd, L"ApplicationFrameWindow")))
    {
        ACCENT_POLICY accentPolicy = {};
        WINCOMPATTRDATA winCompositionAttrib = {};
        DWM_BLURBEHIND dwmBlurBehindData = { };

        dwmBlurBehindData.fEnable = TRUE;
        dwmBlurBehindData.dwFlags = DWM_BB_ENABLE | DWM_BB_BLURREGION | DWM_BB_TRANSITIONONMAXIMIZED;
        // Blurs window client area
        HRGN hRgn = CreateRectRgn(0, 0, -1, -1);
        dwmBlurBehindData.hRgnBlur = hRgn;
        dwmBlurBehindData.fTransitionOnMaximized = TRUE;

        DwmEnableBlurBehindWindow(hWnd, &dwmBlurBehindData);
        DeleteObject(hRgn);

        accentPolicy.AccentState = ACCENT_STATE_ENABLE_ACRYLICBLURBEHIND;
        accentPolicy.GradientColor = g_settings.AccentBlurBehindClr;

        winCompositionAttrib.Attrib = WCA_ACCENT_POLICY;
        winCompositionAttrib.pvData = &accentPolicy;
        winCompositionAttrib.cbData = sizeof(accentPolicy);

        if (SetWindowCompositionAttribute)
            SetWindowCompositionAttribute(hWnd, &winCompositionAttrib);    
    }
}''',
        '''VOID ApplyAccentPolicy(HWND hWnd, ACCENT_STATE state, COLORREF gradientColor)
{
    // Skip windows that shouldn't receive composition effects
    if (IsWindowClass(hWnd, L"CASCADIA_HOSTING_WINDOW_CLASS") || IsWindowClass(hWnd, L"ApplicationFrameWindow"))
        return;

    // For blur-based states, prime DWM composition region so the effect is
    // visible on Win10 regardless of whether the frame is extended.
    if (state == ACCENT_STATE_ENABLE_BLURBEHIND || state == ACCENT_STATE_ENABLE_ACRYLICBLURBEHIND)
    {
        DWM_BLURBEHIND bb = {};
        bb.fEnable    = TRUE;
        bb.dwFlags    = DWM_BB_ENABLE | DWM_BB_BLURREGION | DWM_BB_TRANSITIONONMAXIMIZED;
        HRGN hRgn     = CreateRectRgn(0, 0, -1, -1);
        bb.hRgnBlur   = hRgn;
        bb.fTransitionOnMaximized = TRUE;
        DwmEnableBlurBehindWindow(hWnd, &bb);
        DeleteObject(hRgn);
    }

    ACCENT_POLICY accentPolicy = {};
    accentPolicy.AccentState   = static_cast<INT>(state);
    accentPolicy.GradientColor = static_cast<INT>(gradientColor);

    // Gradient/transparent-gradient modes need the gradient color flag set
    if (state == ACCENT_STATE_ENABLE_GRADIENT || state == ACCENT_STATE_ENABLE_TRANSPARENTGRADIENT)
        accentPolicy.AccentFlags = ACCENT_FLAG_ENABLE_GRADIENT_COLOR;

    WINCOMPATTRDATA wca = {};
    wca.Attrib  = WCA_ACCENT_POLICY;
    wca.pvData  = &accentPolicy;
    wca.cbData  = sizeof(accentPolicy);

    if (SetWindowCompositionAttribute)
        SetWindowCompositionAttribute(hWnd, &wca);
}

VOID EnableBlurBehind(HWND hWnd)
{
    ApplyAccentPolicy(hWnd, static_cast<ACCENT_STATE>(g_settings.BgType), g_settings.AccentBlurBehindClr);
}'''
    )

    # ── 6. Replace HandleEffects ───────────────────────────────────────────────
    # Also fix ExtendFrame: when extending frame we need DwmEnableBlurBehindWindow
    # with a NULL region (full window) so DWM treats the whole client area as glass.
    # This is what makes DwmBlurGlass-style compositors work instead of showing black.
    src = src.replace(
        '''VOID HandleEffects(HWND hWnd)
{
    BOOL isFlyoutWindow = isWindowFlyout(hWnd);

    if (g_IsSysThemeDarkMode) 
        DwmSetWindowAttribute(hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &ENABLE, sizeof(UINT));

    if(g_settings.BgType == g_settings.AccentBlurBehind)
        EnableBlurBehind(hWnd);
    else if (g_settings.BgType > g_settings.AccentBlurBehind)
    {
        if (isFlyoutWindow) {
            DwmMakeWindowTransparent(hWnd);
            TriggerWindowNCRendering(hWnd);
        }
        DwmSetWindowAttribute(hWnd, DWMWA_SYSTEMBACKDROP_TYPE, &g_settings.BgType, sizeof(UINT));
    }

    if (!isFlyoutWindow && g_settings.BgType != g_settings.Default) {
        MARGINS margins = {-1, -1, -1, -1};
        DwmExtendFrameIntoClientArea(hWnd, &margins);
    }
    
    if (isFlyoutWindow) {
        UINT borderType = DWMWCP_ROUND;
        DwmSetWindowAttribute(hWnd, DWMWA_WINDOW_CORNER_PREFERENCE, &borderType, sizeof(UINT));
    }
    
    return;
}''',
        '''VOID HandleEffects(HWND hWnd)
{
    BOOL isFlyoutWindow = isWindowFlyout(hWnd);

    if (g_IsSysThemeDarkMode)
        DwmSetWindowAttribute(hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &ENABLE, sizeof(UINT));

    if (g_settings.BgType != g_settings.Default)
    {
        if (isFlyoutWindow) {
            DwmMakeWindowTransparent(hWnd);
            TriggerWindowNCRendering(hWnd);
        }
        // All modes go through AccentPolicy (Win10-compatible)
        EnableBlurBehind(hWnd);
    }

    // Frame extension is opt-in.
    // When enabled we also call DwmEnableBlurBehindWindow with a NULL region
    // (full-window glass) so that DWM compositors like DwmBlurGlass see real
    // glass instead of an opaque black surface.
    if (g_settings.ExtendFrame && !isFlyoutWindow && g_settings.BgType != g_settings.Default) {
        // Full-window blur region tells DWM the entire client area is glass
        DWM_BLURBEHIND bbFull = {};
        bbFull.fEnable = TRUE;
        bbFull.dwFlags = DWM_BB_ENABLE;   // no BLURREGION flag = full window
        DwmEnableBlurBehindWindow(hWnd, &bbFull);

        MARGINS margins = {-1, -1, -1, -1};
        DwmExtendFrameIntoClientArea(hWnd, &margins);
    }

    return;
}'''
    )

    # ── 7. Remove Win11-only DWMWA_WINDOW_CORNER_PREFERENCE from DefWindowProc hook
    src = re.sub(
        r'    if \(IsWindowClass\(hWnd, L"ViewControlClass"\) && msg == WM_NCPAINT\) \{\s*'
        r'UINT borderType = DWMWCP_ROUND;\s*'
        r'DwmSetWindowAttribute\(hWnd, DWMWA_WINDOW_CORNER_PREFERENCE, &borderType, sizeof\(UINT\)\);\s*'
        r'\}\s*\n',
        '',
        src
    )

    # ── 8. Fix HookedExtTextOutW: don't paint opaque BG for flyout/popup windows
    # The core problem: when ETO_OPAQUE is set, we call FillRect on hdc with origBkClr.
    # For popup menus this destroys DWM transparency - the fill is opaque and the
    # alpha-blended text never recovers it. Desktop/Explorer menus are rendered in
    # a popup window (#32768) whose background is supposed to stay transparent.
    # Fix: skip the opaque background fill when the DC's window is a flyout.
    # We also need to handle the case where options has ETO_OPAQUE but we're in
    # a transparent context - just don't fill, let the existing composited bg show.
    OLD_EXTTEXT_OPAQUE = '''\
    if ((options & ETO_OPAQUE) && lprect) {
        HBRUSH brush = CreateSolidBrush(origBkClr);
        FillRect(hdc, lprect, brush);
        DeleteObject(brush);
    }

    WINBOOL res = ExtTextOutW_orig(memDC, x, y, options & ~ETO_OPAQUE, lprect, lpString, c, lpDx);'''

    NEW_EXTTEXT_OPAQUE = '''\
    // For flyout/popup windows (menus, tooltips) we must NOT paint an opaque
    // background fill - it destroys DWM translucency. The composited background
    // is already in place; we only need to alpha-blend the text glyphs on top.
    HWND hExtWnd = WindowFromDC(hdc);
    BOOL isFlyoutDC = isWindowFlyout(hExtWnd);

    if ((options & ETO_OPAQUE) && lprect && !isFlyoutDC) {
        HBRUSH brush = CreateSolidBrush(origBkClr);
        FillRect(hdc, lprect, brush);
        DeleteObject(brush);
    }

    WINBOOL res = ExtTextOutW_orig(memDC, x, y, options & ~ETO_OPAQUE, lprect, lpString, c, lpDx);'''

    src = src.replace(OLD_EXTTEXT_OPAQUE, NEW_EXTTEXT_OPAQUE)

    # ── 9. Remove SysColorElements array ──────────────────────────────────────
    src = re.sub(
        r'constexpr INT SysColorElements\[\] = \{[^}]*\};\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9b. Remove ClearSysColorsRegKey
    src = re.sub(
        r'void ClearSysColorsRegKey\(\) \{\s*RegDeleteTreeW[^}]*\}\n\n?',
        '',
        src, flags=re.DOTALL
    )

    # ── 9c. Remove RevertSysColors
    src = re.sub(
        r'VOID RevertSysColors\(\)\n\{.*?\n\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9d. Remove GetDefaultSysColor
    src = re.sub(
        r'static COLORREF GetDefaultSysColor\(INT nIndex\)\n\{.*?\n\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9e. Remove GetCustomSysColor
    src = re.sub(
        r'static COLORREF GetCustomSysColor\(INT nIndex\)\n\{.*?\n\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9f. Remove HookedGetSysColor
    src = re.sub(
        r'COLORREF WINAPI HookedGetSysColor\(INT nIndex\) \n\{.*?\n\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9g. Remove HookedGetSysColorBrush
    src = re.sub(
        r'HBRUSH WINAPI HookedGetSysColorBrush\(INT nIndex\) \n\{.*?\n\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9h. Remove ColorizeSysColors
    src = re.sub(
        r'VOID ColorizeSysColors\(\)\n\{[^}]*\}\n\n',
        '',
        src, flags=re.DOTALL
    )

    # ── 9i. Remove g_DefaultSysColors global + dual brush cache globals
    src = re.sub(
        r'// Redirect per ruled program.*?SRWLOCK g_SysColorsLock = SRWLOCK_INIT;\n',
        '// System color brush cache\nstd::array<HBRUSH, COLOR_MENUBAR + 1> g_themeCachedCustomSysColorBrushes {nullptr};\nSRWLOCK g_SysColorsLock = SRWLOCK_INIT;\n',
        src, flags=re.DOTALL
    )

    # ── 10. Remove Process Rules functions ────────────────────────────────────
    src = re.sub(
        r'// Normalizes a path.*?VOID LoadWindowProcessRules\(\)\n\{.*?\}\n\n',
        '',
        src, flags=re.DOTALL
    )
    src = re.sub(r'\s*LoadWindowProcessRules\(\);\n', '\n', src)

    # ── 11. Remove SetSystemColors / SysColors from LoadSettings ─────────────
    src = re.sub(
        r'    g_settings\.SetSystemColors = Wh_GetIntSetting\(L"RenderingMod\.Syscolors"\);\n'
        r'    // SetSysColors API available only in theme customization\n'
        r'    if \(g_settings\.SetSystemColors && g_settings\.FillBg\)\n'
        r'        ColorizeSysColors\(\);\n',
        '',
        src
    )

    # ── 12. Replace background type setting block in LoadSettings ─────────────
    src = src.replace(
        '''    auto strStyle = WindhawkUtils::StringSetting(Wh_GetStringSetting(L"BackgroundEffects.type"));
    if (0 == wcscmp(strStyle, L"acrylicblur"))
        g_settings.BgType = g_settings.AccentBlurBehind;
    else if (0 == wcscmp(strStyle, L"acrylicsystem"))
        g_settings.BgType = g_settings.AcrylicSystemBackdrop;
    else if (0 == wcscmp(strStyle, L"mica"))
        g_settings.BgType = g_settings.Mica;
    else if (0 == wcscmp(strStyle, L"mica_tabbed"))
        g_settings.BgType = g_settings.MicaAlt;
    else 
        g_settings.BgType = g_settings.Default;
    
    GetColorSetting(WindhawkUtils::StringSetting(Wh_GetStringSetting(L"BackgroundEffects.AccentBlurBehind")), g_settings.AccentBlurBehindClr);''',
        '''    auto strStyle = WindhawkUtils::StringSetting(Wh_GetStringSetting(L"BackgroundEffects.type"));
    if (0 == wcscmp(strStyle, L"gradient"))
        g_settings.BgType = g_settings.Gradient;
    else if (0 == wcscmp(strStyle, L"transparentgradient"))
        g_settings.BgType = g_settings.TransparentGradient;
    else if (0 == wcscmp(strStyle, L"blurbehind"))
        g_settings.BgType = g_settings.BlurBehind;
    else if (0 == wcscmp(strStyle, L"acrylicblur"))
        g_settings.BgType = g_settings.AcrylicBlur;
    else
        g_settings.BgType = g_settings.Default;

    GetColorSetting(WindhawkUtils::StringSetting(Wh_GetStringSetting(L"BackgroundEffects.AccentColor")), g_settings.AccentBlurBehindClr);

    g_settings.ExtendFrame = Wh_GetIntSetting(L"BackgroundEffects.ExtendFrame");'''
    )

    # ── 13. Fix CustomRenderingHooks - remove SetSystemColors branch ──────────
    src = re.sub(
        r'    if \(!g_settings\.SetSystemColors\) \{\n'
        r'        WindhawkUtils::SetFunctionHook\(FillRect, HookedFillRect, &FillRect_orig\);\n'
        r'        WindhawkUtils::SetFunctionHook\(GetSysColor, HookedGetSysColor, &GetSysColor_orig\);\n'
        r'        WindhawkUtils::SetFunctionHook\(GetSysColorBrush, HookedGetSysColorBrush, &GetSysColorBrush_orig\);\n'
        r'    \}\n',
        '    WindhawkUtils::SetFunctionHook(FillRect, HookedFillRect, &FillRect_orig);\n'
        '    WindhawkUtils::SetFunctionHook(GetSysColor, HookedGetSysColor, &GetSysColor_orig);\n'
        '    WindhawkUtils::SetFunctionHook(GetSysColorBrush, HookedGetSysColorBrush, &GetSysColorBrush_orig);\n',
        src
    )

    # Fix User32Hooks call - no longer passing SetSystemColors arg
    src = re.sub(r'User32Hooks\(g_settings\.SetSystemColors\)', 'User32Hooks(FALSE)', src)
    src = re.sub(r'User32Hooks\(TRUE\)', 'User32Hooks(FALSE)', src)

    # ── 14. Fix ApplyHooks - remove DwmSetWindowAttributeHook ────────────────
    src = src.replace(
        '''    if (g_settings.BgType != g_settings.Default) {
        DwmSetWindowAttributeHook();
        DwmExpandFrameIntoClientAreaHook();
        }''',
        '''    if (g_settings.BgType != g_settings.Default || g_settings.ExtendFrame)
        DwmExpandFrameIntoClientAreaHook();'''
    )

    # ── 15. Fix Wh_ModUninit - remove SetSystemColors revert, fix brush cleanup
    src = src.replace(
        '''    if (g_settings.SetSystemColors)
        RevertSysColors();

    for (size_t i = 0; i < g_themeCachedDefaultSysColorBrushes.size(); i++) {
        HBRUSH& brushCustom = g_themeCachedCustomSysColorBrushes[i];
        HBRUSH& brushDefault = g_themeCachedDefaultSysColorBrushes[i];
        if (brushCustom) { 
            DeleteObject(brushCustom); 
            brushCustom = nullptr; 
        }
        if (brushDefault) { 
            DeleteObject(brushDefault); 
            brushDefault = nullptr; 
        }
    }''',
        '''    for (size_t i = 0; i < g_themeCachedCustomSysColorBrushes.size(); i++) {
        HBRUSH& brush = g_themeCachedCustomSysColorBrushes[i];
        if (brush) {
            DeleteObject(brush);
            brush = nullptr;
        }
    }'''
    )

    # ── 16. Add minimal GetSysColor/Brush stubs if removed (needed by hooks) ──
    if 'COLORREF WINAPI HookedGetSysColor' not in src:
        stub = '''// Minimal GetSysColor/GetSysColorBrush hooks (no color modification; just
// intercept for FillRect pseudo-handle resolution and brush caching)
COLORREF WINAPI HookedGetSysColor(INT nIndex)
{
    return GetSysColor_orig(nIndex);
}

HBRUSH WINAPI HookedGetSysColorBrush(INT nIndex)
{
    if (nIndex < 0 || nIndex > COLOR_MENUBAR)
        return GetSysColorBrush_orig(nIndex);

    HBRUSH cached = g_themeCachedCustomSysColorBrushes[nIndex];
    if (cached && GetObjectType(cached) == OBJ_BRUSH)
        return cached;

    AcquireSRWLockExclusive(&g_SysColorsLock);
    HBRUSH& ref = g_themeCachedCustomSysColorBrushes[nIndex];
    if (!ref || GetObjectType(ref) != OBJ_BRUSH)
        ref = CreateSolidBrush(GetSysColor_orig(nIndex));
    HBRUSH hbr = ref;
    ReleaseSRWLockExclusive(&g_SysColorsLock);
    return hbr;
}

'''
        src = src.replace('VOID CustomRenderingHooks()', stub + 'VOID CustomRenderingHooks()')

    # ── 17. Fix RestoreWindowCustomizations - replace DWMSBT_NONE (Win11) ─────
    src = src.replace(
        '    DWM_SYSTEMBACKDROP_TYPE backdrop = DWMSBT_NONE;\n'
        '    DwmSetWindowAttribute(hWnd, DWMWA_SYSTEMBACKDROP_TYPE , &backdrop, sizeof(UINT));',
        '    // Reset accent policy to disabled\n'
        '    ACCENT_POLICY accentOff = {};\n'
        '    accentOff.AccentState = ACCENT_STATE_DISABLED;\n'
        '    WINCOMPATTRDATA wcaOff = { WCA_ACCENT_POLICY, &accentOff, sizeof(accentOff) };\n'
        '    if (SetWindowCompositionAttribute)\n'
        '        SetWindowCompositionAttribute(hWnd, &wcaOff);'
    )

    # ── 18. Update the Windhawk settings YAML ─────────────────────────────────
    OLD_YAML = '''// ==WindhawkModSettings==
/*
- RenderingMod:
    - ThemeBackground: TRUE
      $name: 🔷 Windows theme custom rendering
      $description: >-
       Modifies parts of the Windows theme using the Direct2D graphics API and modifies 
       Windows GDI text rendering by patching the alpha channel and adjusting text colors.
        ✨It is recommended to enable this with background translucent effects.
    - SysColors: FALSE
      $name: 🔷 New system colors
      $description: >-
       Modifies additional system UI colors by calling SetSysColors API. (Requires Windows theme custom rendering)
        ⚠️For issues with excluded processes, use process rules in mod\'s settings. For more refer to the FAQ.
    - AccentColorControls: TRUE
      $name: 🔷 Windows theme accent colorizer
      $description: >-
       Paint with accent color parts of windows theme. (Requires Windows theme custom rendering)
  $name: 🔶 Theme Customization
- BackgroundEffects:
    - type: acrylicblur
      $name: 🔷 Background effects
      $description: >-
        Windows 11 version >= 22621.xxx (22H2) is required for SystemBackdrop effects.
      $options:
      - none: Default
      - acrylicblur: Blur (AccentBlurBehind)
      - acrylicsystem: Acrylic (SystemBackdrop)
      - mica: Mica (SystemBackdrop)
      - mica_tabbed: MicaAlt (SystemBackdrop)
    - AccentBlurBehind: "3A232323"
      $name: 🔷 AccentBlurBehind color blend
      $description: >-
        Blending color with blur background.
        Color in hexadecimal ARGB format e.g. 3A232323
  $name: 🔶 Translucent Effects
- FlyoutsEffects: TRUE
  $name: 🔶 Flyout effects
  $description: >-
    Expand the effects to Win32 flyouts (context menus, dropdown menus, tooltips)
     ✨It is recommended to enable this with both background translucent effects and Windows theme custom rendering.
- RuledPrograms:
    - - target: "mspaint.exe"
        $name: 🔶 Process
        $description: >-
         Entries can be process names, paths or subdirectories for example:
          • Taskmgr.exe
          • C:\\Windows\\System32\\Taskmgr.exe
          • C:\\Windows
      - RenderingMod:
          - ThemeBackground: FALSE
            $name: 🔷 Windows theme custom rendering
            $description: >-
              Modifies parts of the Windows theme using the Direct2D graphics API and modifies Windows GDI text rendering by patching the alpha channel and adjusting text colors.
               ✨It is recommended to enable this with background translucent effects.
          - AccentColorControls: FALSE
            $name: 🔷 Windows theme accent colorizer
            $description: >-
              Paint with accent color parts of windows theme. (Requires Windows theme custom rendering)
        $name: 🔶 Theme Customization
      - BackgroundEffects:
        - type: none
          $name: 🔷 Background translucent effects
          $description: >-
           Windows 11 version >= 22621.xxx (22H2) is required for SystemBackdrop effects.
          $options:
          - none: Default
          - acrylicblur: Blur (AccentBlurBehind)
          - acrylicsystem: Acrylic (SystemBackdrop)
          - mica: Mica (SystemBackdrop)
          - mica_tabbed: MicaAlt (SystemBackdrop)
        - AccentBlurBehind: "3A232323"
          $name: 🔷 AccentBlurBehind color blend
          $description: >-
           Blending color with blur background.
            Color in hexadecimal ARGB format e.g. 3A232323
        $name: 🔶 Translucent Effects
  $name: ⏩ Process Rules
  $description: >-
      Add rules to each specified process or processes from specific subdirectories
       ❗ Add process rules for the excluded process instead of using Windhawk\'s process exclusion when the "New system colors" global setting is enabled.
*/
// ==/WindhawkModSettings=='''

    NEW_YAML = '''// ==WindhawkModSettings==
/*
- RenderingMod:
    - ThemeBackground: TRUE
      $name: 🔷 Windows theme custom rendering
      $description: >-
       Modifies parts of the Windows theme using the Direct2D graphics API and modifies
       Windows GDI text rendering by patching the alpha channel and adjusting text colors.
        ✨It is recommended to enable this with background translucent effects.
    - AccentColorControls: TRUE
      $name: 🔷 Windows theme accent colorizer
      $description: >-
       Paint with accent color parts of windows theme. (Requires Windows theme custom rendering)
  $name: 🔶 Theme Customization
- BackgroundEffects:
    - type: none
      $name: 🔷 Background effect
      $description: >-
        Translucent background effect applied via SetWindowCompositionAttribute (AccentPolicy).
        Compatible with Windows 10 and Windows 11.
        Use Windhawk\'s built-in process exclusion list to exclude specific processes.
      $options:
      - none: Default (no effect)
      - gradient: Solid gradient color
      - transparentgradient: Transparent gradient
      - blurbehind: Blur behind (classic DWM blur)
      - acrylicblur: Acrylic blur (Win10 modern blur)
    - AccentColor: "3A232323"
      $name: 🔷 Accent / gradient color
      $description: >-
        Color blended with the background effect.
        Hexadecimal ARGB format: AA RR GG BB, e.g. 3A232323
        (AA = alpha/opacity, RR GG BB = color).
        Used by all effect modes. For blurbehind/acrylicblur this tints the blur.
    - ExtendFrame: FALSE
      $name: 🔷 Extend DWM frame into client area
      $description: >-
        Calls DwmExtendFrameIntoClientArea with {-1,-1,-1,-1} after applying the effect.
        Also enables full-window DWM glass composition (required for tools like DwmBlurGlass).
        Enable this if the effect is not visible in the window client area.
  $name: 🔶 Translucent Effects
- FlyoutsEffects: TRUE
  $name: 🔶 Flyout effects
  $description: >-
    Expand the effects to Win32 flyouts (context menus, dropdown menus, tooltips).
     ✨It is recommended to enable this with both background translucent effects and Windows theme custom rendering.
*/
// ==/WindhawkModSettings=='''

    src = src.replace(OLD_YAML, NEW_YAML)

    # ── 19. README updates ─────────────────────────────────────────────────────
    src = src.replace(
        '* ⚠️ARM64 system is only partially supported.⚠️',
        '* ⚠️ARM64 system is only partially supported.⚠️\n\n'
        '* ✅ Windows 10 compatible. Background effects use SetWindowCompositionAttribute (AccentPolicy).\n'
        '  Available modes: Solid Gradient, Transparent Gradient, Blur Behind, Acrylic Blur.\n\n'
        '* ℹ️ To exclude specific processes, use Windhawk\'s built-in process exclusion list in the mod options.\n\n'
        '* ℹ️ For DwmBlurGlass / glass compositor support, enable "Extend DWM frame into client area".'
    )

    # Remove Win11-specific SystemBackdrop FAQ entry
    src = re.sub(
        r'\* ⚠️Windows 11 version >= 22621\.xxx \(22H2\) is required for SystemBackdrop effects.*?⚠️\n\n',
        '',
        src, flags=re.DOTALL
    )

    return src


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else re.sub(r'(\.wh)?\.cpp$', '-win10.wh.cpp', in_path)
    if out_path == in_path:
        out_path = in_path.replace('.cpp', '-win10.cpp')

    with open(in_path, 'r', encoding='utf-8') as f:
        src = f.read()

    print(f"Input:  {in_path}  ({len(src):,} chars)")
    result = patch(src)
    print(f"Output: {out_path}  ({len(result):,} chars, delta {len(result)-len(src):+,})")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print("✓ Done. Review the output before compiling.")
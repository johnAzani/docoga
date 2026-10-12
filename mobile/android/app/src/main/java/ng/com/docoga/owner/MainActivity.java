package ng.com.docoga.owner;

import android.os.Build;
import android.os.Bundle;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;

/**
 * The whole app, in one file — and this file is still not where the product lives.
 *
 * DocOga Owner is a signed door to https://docoga.com.ng/admin (see
 * mobile/capacitor.config.json → server.url). Loading the page from the network
 * rather than bundling it is a deliberate security choice, not a shortcut:
 *
 *   • nothing on the phone can be reversed into access. There is no passphrase,
 *     no token and no key in this APK, so a lost phone, a leaked APK or a copied
 *     install are all harmless — the session lives in the WebView's own storage
 *     and dies with a server-side "sign out every other device".
 *   • the dashboard updates when the SITE updates. A bug fix or a new revenue
 *     card reaches your phone the moment Cloudflare serves it; there is no
 *     rebuild, no re-download, no reinstall, and no old APK floating around
 *     still showing last month's numbers.
 *   • Capacitor ships no native code here, so the attack surface is the system
 *     WebView (patched by Play) rather than a bundled Chromium frozen at build
 *     time.
 *
 * What this override is for: the back gesture. Capacitor 8.5.3 does not touch
 * navigation, so the default behaviour is "back = close the app". On Android 16
 * (targetSdk 36) onBackPressed is no longer called at all — predictive back is
 * enabled and the gesture must be claimed through OnBackInvokedDispatcher — so
 * both paths are implemented and both delegate to the WebView, which is where the
 * history actually is.
 */
public class MainActivity extends BridgeActivity {

  /* Held in a field on purpose: the dispatcher matches on identity, and a method
   * reference builds a new object every time it is written — so registering
   * `this::goBackOrLeave` and unregistering `this::goBackOrLeave` would leak the
   * callback instead of removing it. */
  private final Runnable backCallback = this::goBackOrLeave;

  @Override
  public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    if (Build.VERSION.SDK_INT >= 33) {
      getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
        android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback
      );
    }
  }

  @Override
  protected void onDestroy() {
    if (Build.VERSION.SDK_INT >= 33) {
      try {
        getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(backCallback);
      } catch (Exception ignored) { /* already detached — nothing left to release */ }
    }
    super.onDestroy();
  }

  /** Legacy path: below 33 the back gesture still arrives as onBackPressed. */
  @Override
  @SuppressWarnings("deprecation")
  public void onBackPressed() {
    if (Build.VERSION.SDK_INT < 33) goBackOrLeave();
    else super.onBackPressed();
  }

  /** Walk back through the page's own history; leave the app at the root.
   *  The dashboard is a single view with no deep links today, so in practice
   *  "back" closes the app — the guard exists so that the day the page starts
   *  pushing history, the gesture follows it instead of escaping. */
  private void goBackOrLeave() {
    Bridge b = getBridge();
    WebView wv = b == null ? null : b.getWebView();
    if (wv != null && wv.canGoBack()) {
      wv.goBack();
      return;
    }
    // MoveTaskToBack keeps the WebView (and its session) warm for the next tap
    // on the icon, which is what makes a 12-hour token feel like a native app.
    moveTaskToBack(true);
  }
}

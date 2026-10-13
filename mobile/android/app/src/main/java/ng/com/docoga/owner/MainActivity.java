package ng.com.docoga.owner;

import android.annotation.SuppressLint;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebView;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;
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
 * What this override is for: the back gesture. Capacitor 8.5.3 implements no
 * back handling at all, so the default is "back = close the app". On Android 16
 * (targetSdk 36) onBackPressed is not even delivered — predictive back is on and
 * the gesture must be claimed through OnBackInvokedCallback — so both paths exist
 * here and both delegate to the WebView, which is where the history actually is.
 */
/* The API-33 symbols (OnBackInvokedCallback / getOnBackInvokedDispatcher) sit
 * behind explicit Build.VERSION.SDK_INT checks; that is what makes them safe at
 * runtime on minSdk 24. Annotated at class level so the check is stated once, in
 * the place a reader will look for it, rather than scattered per call site. */
@SuppressLint("NewApi")
public class MainActivity extends BridgeActivity {

  /* Must be OnBackInvokedCallback, not Runnable: registerOnBackInvokedCallback
   * takes that interface, and a Runnable — even one bound to the same method —
   * is simply the wrong type. Held in a field on purpose too, because the
   * dispatcher matches on identity when unregistering, and writing
   * `this::goBackOrLeave` twice builds two different objects (the second would
   * unregister nothing and leak the first).
   *
   * The type does not exist below API 33 while minSdk is 24. That is safe: ART
   * resolves it lazily, so a field whose *declared type* is newer than the
   * device is fine as long as nothing touches it — which is what every use of
   * this field below is guarded by. (This is the same pattern AndroidX uses.) */
  private OnBackInvokedCallback backCallback;

  @Override
  public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    if (Build.VERSION.SDK_INT >= 33) {
      // PRIORITY_DEFAULT is a constant of the *dispatcher* interface, not of the
      // callback — and the callback is written out instead of as a lambda so the
      // build depends on nothing newer than the template's default Java level.
      backCallback = new OnBackInvokedCallback() {
        @Override public void onBackInvoked() { goBackOrLeave(); }
      };
      getOnBackInvokedDispatcher()
        .registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback);
    }
  }

  /* public, not protected: BridgeActivity.onDestroy() is public, and narrowing an
   * override's visibility is a javac error ("weaker access privileges") — the
   * mistake CI caught in one build minute that no local grep could have found. */
  @Override
  public void onDestroy() {
    if (Build.VERSION.SDK_INT >= 33 && backCallback != null) {
      try {
        getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(backCallback);
      } catch (Exception ignored) { /* already detached — nothing left to release */ }
      backCallback = null;
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
   *  "back" backgrounds the app — the guard exists so that the day the page
   *  starts pushing history, the gesture follows it instead of escaping. */
  private void goBackOrLeave() {
    Bridge b = getBridge();
    WebView wv = b == null ? null : b.getWebView();
    if (wv != null && wv.canGoBack()) {
      wv.goBack();
      return;
    }
    // moveTaskToBack keeps the WebView (and its session) warm for the next tap on
    // the icon, which is what makes a 12-hour token feel like a native app.
    moveTaskToBack(true);
  }
}

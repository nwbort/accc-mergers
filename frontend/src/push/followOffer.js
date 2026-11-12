// The hook between following and browser notifications.
//
// TrackingContext calls notifyFollowed() from inside the click that follows
// something; PushContext registers the handler that, the first time, asks the
// browser for permission. It has to run in that click: browsers only show the
// permission prompt in response to a user's action.
//
// A plain module rather than context because TrackingProvider sits above
// PushProvider, which needs its state.

let handler = null;

/** Register the follow handler; returns a function that removes it. */
export function setFollowHandler(fn) {
  handler = fn;
  return () => {
    if (handler === fn) handler = null;
  };
}

/** Something was just followed, by the person, in this click. */
export function notifyFollowed() {
  try {
    if (handler) handler();
  } catch (err) {
    console.error('Follow handler failed:', err);
  }
}

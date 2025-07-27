/**
 * Vue directive to detect clicks outside of an element.
 *
 * Usage:
 * <div v-click-outside="myMethod">...</div>
 *
 * The 'myMethod' will be called when a click occurs outside the div.
 */
const clickOutside = {
  beforeMount(el, binding) {
    el.clickOutsideEvent = function (event) {
      // here I check that click was outside the el and his children
      if (!(el === event.target || el.contains(event.target))) {
        // and if it did, call method provided in attribute value
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.clickOutsideEvent);
  },
  unmounted(el) {
    document.body.removeEventListener('click', el.clickOutsideEvent);
  },
};

export default clickOutside;
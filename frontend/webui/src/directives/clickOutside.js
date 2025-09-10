/**
 * v-on-click-outside
 * A Vue directive to call a method when a click occurs outside the bound element.
 */
export default {
  beforeMount: (el, binding) => {
    el.clickOutsideEvent = event => {
      // Check if the click is outside the element and its binding's context
      if (!(el === event.target || el.contains(event.target))) {
        // Call the method provided in the directive's value
        binding.value(event);
      }
    };
    // Add event listener to the whole document
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    // Clean up the event listener
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};
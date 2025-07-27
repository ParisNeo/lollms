import { ref } from 'vue';

const bus = ref(new Map());

export default function useEventBus() {
    const emit = (event, ...args) => {
        const handlers = bus.value.get(event);
        if (handlers) {
            handlers.forEach(handler => handler(...args));
        }
    };

    const on = (event, handler) => {
        if (!bus.value.has(event)) {
            bus.value.set(event, []);
        }
        bus.value.get(event).push(handler);
    };

    const off = (event, handler) => {
        const handlers = bus.value.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    };

    return { emit, on, off };
}
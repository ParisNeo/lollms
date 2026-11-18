import { computed } from 'vue';
import { useAuthStore } from '../stores/auth';

/**
 * Reusable accessor for admin Settings Policy state.
 *
 * Usage in any settings component:
 *
 *   <script setup>
 *   import { useSettingsPolicy } from '../../composables/useSettingsPolicy';
 *   const { isLocked, isForced, forcedValue, policyTitle, lockedFields } = useSettingsPolicy();
 *   </script>
 *
 *   <template>
 *     <input :disabled="isLocked('memory_enabled')" ... />
 *     <span v-if="isLocked('memory_enabled')" class="lock-hint">{{ policyTitle('memory_enabled') }}</span>
 *   </template>
 *
 * A field is "locked" when an admin has locked it OR pinned a forced value;
 * in both cases the user cannot change it. Writes are additionally blocked in
 * `authStore.updateUserPreferences` and by the backend
 * (`apply_policies_to_update`), so this composable is purely for presentation.
 */
export function useSettingsPolicy() {
    const authStore = useAuthStore();

    /** True when the field is locked or forced — the user cannot edit it. */
    const isLocked = (field) => authStore.isFieldLocked(field);

    /** True when an admin pinned a concrete value for the field. */
    const isForced = (field) => authStore.isFieldForced(field);

    /** The pinned value for a forced field (undefined when not forced). */
    const forcedValue = (field) => authStore.fieldPolicy(field)?.forced_value;

    /** Human-readable tooltip explaining why a field is disabled. */
    const policyTitle = (field) => {
        const policy = authStore.fieldPolicy(field);
        if (!policy) return '';
        if (policy.forced) return `Managed by administrator (pinned to: ${policy.forced_value})`;
        if (policy.locked) return 'Locked by administrator';
        return '';
    };

    /** Set of field names the current user cannot change (reactive). */
    const lockedFields = computed(() => {
        const out = new Set();
        for (const [name, p] of Object.entries(authStore.settingsPolicy || {})) {
            if (p?.locked || p?.forced) out.add(name);
        }
        return out;
    });

    return { isLocked, isForced, forcedValue, policyTitle, lockedFields };
}
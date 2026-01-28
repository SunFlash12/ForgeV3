// Forge Cascade - Cart Store (Zustand)
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MarketplaceCapsule, CartItem } from '../types/marketplace';
import type { TrustLevel, CapsuleType } from '../types';

const PLATFORM_FEE_RATE = 0.10; // 10% platform fee

/**
 * SECURITY FIX (Audit 4 - M13): Sanitize string to prevent XSS
 * Removes any HTML/script tags and dangerous characters
 */
function sanitizeString(input: unknown): string {
  if (typeof input !== 'string') return '';
  return input
    .replace(/<[^>]*>/g, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .slice(0, 1000);
}

/**
 * SECURITY FIX (Audit 4 - M13): Validate and sanitize cart item from localStorage
 * Prevents XSS through malicious data injection in localStorage
 */
function validateCartItem(item: unknown): CartItem | null {
  if (!item || typeof item !== 'object') return null;

  const obj = item as Record<string, unknown>;

  if (!obj.capsule || typeof obj.capsule !== 'object') return null;

  const capsule = obj.capsule as Record<string, unknown>;

  // Validate capsule id is a valid UUID
  if (typeof capsule.id !== 'string' || !/^[a-f0-9-]{36}$/i.test(capsule.id)) {
    return null;
  }

  const validTrustLevels: TrustLevel[] = ['QUARANTINE', 'SANDBOX', 'STANDARD', 'TRUSTED', 'CORE'];
  const trustLevel = typeof capsule.trust_level === 'string' && validTrustLevels.includes(capsule.trust_level as TrustLevel)
    ? capsule.trust_level as TrustLevel
    : 'SANDBOX';

  const validTypes: CapsuleType[] = ['INSIGHT', 'DECISION', 'LESSON', 'WARNING', 'PRINCIPLE', 'MEMORY', 'KNOWLEDGE', 'CODE', 'CONFIG', 'TEMPLATE', 'DOCUMENT'];
  const capsuleType = typeof capsule.type === 'string' && validTypes.includes(capsule.type as CapsuleType)
    ? capsule.type as CapsuleType
    : 'KNOWLEDGE';

  const sanitizedCapsule: MarketplaceCapsule = {
    id: capsule.id,
    title: sanitizeString(capsule.title),
    content: sanitizeString(capsule.content) || '',
    description: sanitizeString(capsule.description),
    category: sanitizeString(capsule.category),
    type: capsuleType,
    owner_id: typeof capsule.owner_id === 'string' ? capsule.owner_id.slice(0, 100) : (typeof capsule.author_id === 'string' ? capsule.author_id.slice(0, 100) : ''),
    author_id: typeof capsule.author_id === 'string' ? capsule.author_id.slice(0, 100) : undefined,
    author_name: sanitizeString(capsule.author_name),
    trust_level: trustLevel,
    version: typeof capsule.version === 'string' ? capsule.version.slice(0, 50) : '1.0.0',
    parent_id: typeof capsule.parent_id === 'string' ? capsule.parent_id : null,
    view_count: typeof capsule.view_count === 'number' ? capsule.view_count : 0,
    fork_count: typeof capsule.fork_count === 'number' ? capsule.fork_count : 0,
    access_count: typeof capsule.access_count === 'number' ? capsule.access_count : undefined,
    is_archived: typeof capsule.is_archived === 'boolean' ? capsule.is_archived : false,
    is_public: typeof capsule.is_public === 'boolean' ? capsule.is_public : undefined,
    price: typeof capsule.price === 'number' && capsule.price >= 0 ? capsule.price : 0,
    created_at: typeof capsule.created_at === 'string' ? capsule.created_at : new Date().toISOString(),
    updated_at: typeof capsule.updated_at === 'string' ? capsule.updated_at : new Date().toISOString(),
    tags: Array.isArray(capsule.tags)
      ? capsule.tags.filter((t): t is string => typeof t === 'string').map(sanitizeString).slice(0, 20)
      : [],
    metadata: typeof capsule.metadata === 'object' && capsule.metadata !== null
      ? capsule.metadata as Record<string, unknown>
      : {},
  };

  return {
    capsule: sanitizedCapsule,
    quantity: typeof obj.quantity === 'number' && obj.quantity > 0 ? Math.min(obj.quantity, 100) : 1,
    added_at: obj.added_at instanceof Date ? obj.added_at : new Date(),
  };
}

/**
 * Calculate cart total (CLIENT-SIDE ONLY - FOR DISPLAY PURPOSES)
 *
 * The server MUST independently verify all prices at checkout time.
 * NEVER trust client-submitted prices for actual transactions.
 */
function calculateTotal(items: CartItem[]): number {
  const subtotal = items.reduce((sum, item) => sum + (item.capsule.price || 0), 0);
  return subtotal + (subtotal * PLATFORM_FEE_RATE);
}

interface CartState {
  items: CartItem[];
  total: number;
  itemCount: number;
  addItem: (capsule: MarketplaceCapsule) => void;
  removeItem: (capsuleId: string) => void;
  clearCart: () => void;
  isInCart: (capsuleId: string) => boolean;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      total: 0,
      itemCount: 0,

      addItem: (capsule: MarketplaceCapsule) => {
        const { items } = get();
        if (items.some(item => item.capsule.id === capsule.id)) return;
        const newItems = [...items, { capsule, quantity: 1, added_at: new Date() }];
        set({
          items: newItems,
          total: calculateTotal(newItems),
          itemCount: newItems.length,
        });
      },

      removeItem: (capsuleId: string) => {
        const { items } = get();
        const newItems = items.filter(item => item.capsule.id !== capsuleId);
        set({
          items: newItems,
          total: calculateTotal(newItems),
          itemCount: newItems.length,
        });
      },

      clearCart: () => {
        set({ items: [], total: 0, itemCount: 0 });
      },

      isInCart: (capsuleId: string) => {
        return get().items.some(item => item.capsule.id === capsuleId);
      },
    }),
    {
      name: 'forge_shop_cart',
      // Custom deserialization with validation
      merge: (_persistedState, currentState) => {
        const persisted = _persistedState as Partial<CartState> | undefined;
        if (!persisted?.items || !Array.isArray(persisted.items)) {
          return currentState;
        }

        // Limit number of items
        const MAX_CART_ITEMS = 100;
        const rawItems = persisted.items.slice(0, MAX_CART_ITEMS);

        // Validate and sanitize each item
        const validItems: CartItem[] = [];
        for (const item of rawItems) {
          const validated = validateCartItem(item);
          if (validated) {
            validItems.push(validated);
          }
        }

        return {
          ...currentState,
          items: validItems,
          total: calculateTotal(validItems),
          itemCount: validItems.length,
        };
      },
    }
  )
);

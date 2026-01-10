// Forge Shop - Cart Context
import React, { createContext, useContext, useReducer, useEffect } from 'react';
import type { Capsule, CartItem } from '../types';

interface CartState {
  items: CartItem[];
  total: number;
  itemCount: number;
}

type CartAction =
  | { type: 'ADD_ITEM'; payload: Capsule }
  | { type: 'REMOVE_ITEM'; payload: string }
  | { type: 'CLEAR_CART' }
  | { type: 'LOAD_CART'; payload: CartItem[] };

interface CartContextType extends CartState {
  addItem: (capsule: Capsule) => void;
  removeItem: (capsuleId: string) => void;
  clearCart: () => void;
  isInCart: (capsuleId: string) => boolean;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

const CART_STORAGE_KEY = 'forge_shop_cart';
const PLATFORM_FEE_RATE = 0.10; // 10% platform fee

/**
 * SECURITY FIX (Audit 4 - M13): Sanitize string to prevent XSS
 * Removes any HTML/script tags and dangerous characters
 */
function sanitizeString(input: unknown): string {
  if (typeof input !== 'string') return '';
  // Remove HTML tags, script content, and potentially dangerous patterns
  return input
    .replace(/<[^>]*>/g, '')  // Remove HTML tags
    .replace(/javascript:/gi, '')  // Remove javascript: protocol
    .replace(/on\w+\s*=/gi, '')  // Remove event handlers like onclick=
    .slice(0, 1000);  // Limit length to prevent memory issues
}

/**
 * SECURITY FIX (Audit 4 - M13): Validate and sanitize cart item from localStorage
 * Prevents XSS through malicious data injection in localStorage
 */
function validateCartItem(item: unknown): CartItem | null {
  if (!item || typeof item !== 'object') return null;

  const obj = item as Record<string, unknown>;

  // Validate capsule exists and has required fields
  if (!obj.capsule || typeof obj.capsule !== 'object') return null;

  const capsule = obj.capsule as Record<string, unknown>;

  // Validate capsule id is a valid string (UUID format)
  if (typeof capsule.id !== 'string' || !/^[a-f0-9-]{36}$/i.test(capsule.id)) {
    return null;
  }

  // Sanitize all string fields to prevent XSS
  const sanitizedCapsule: Capsule = {
    id: capsule.id,
    title: sanitizeString(capsule.title),
    description: sanitizeString(capsule.description),
    category: sanitizeString(capsule.category),
    author_id: typeof capsule.author_id === 'string' ? capsule.author_id.slice(0, 100) : '',
    author_name: sanitizeString(capsule.author_name),
    price: typeof capsule.price === 'number' && capsule.price >= 0 ? capsule.price : 0,
    trust_level: typeof capsule.trust_level === 'number' ? capsule.trust_level : 0,
    created_at: typeof capsule.created_at === 'string' ? capsule.created_at : new Date().toISOString(),
    tags: Array.isArray(capsule.tags)
      ? capsule.tags.filter((t): t is string => typeof t === 'string').map(sanitizeString).slice(0, 20)
      : [],
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
 * SECURITY WARNING (Audit 4 - H23): This client-side calculation is for
 * display purposes ONLY. The server MUST independently verify all prices
 * at checkout time by fetching current prices from the database.
 *
 * NEVER trust client-submitted prices for actual transactions.
 * The checkout API endpoint must:
 * 1. Extract capsule IDs from the cart
 * 2. Fetch current prices from the database
 * 3. Calculate the actual total server-side
 * 4. Compare with client total and reject if significantly different
 */
function calculateTotal(items: CartItem[]): number {
  // CLIENT-SIDE ONLY - Server must recalculate from database prices
  const subtotal = items.reduce((sum, item) => sum + (item.capsule.price || 0), 0);
  return subtotal + (subtotal * PLATFORM_FEE_RATE);
}

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'ADD_ITEM': {
      // Don't add duplicates
      if (state.items.some(item => item.capsule.id === action.payload.id)) {
        return state;
      }
      const newItems = [
        ...state.items,
        { capsule: action.payload, quantity: 1, added_at: new Date() },
      ];
      return {
        items: newItems,
        total: calculateTotal(newItems),
        itemCount: newItems.length,
      };
    }
    case 'REMOVE_ITEM': {
      const newItems = state.items.filter(item => item.capsule.id !== action.payload);
      return {
        items: newItems,
        total: calculateTotal(newItems),
        itemCount: newItems.length,
      };
    }
    case 'CLEAR_CART':
      return { items: [], total: 0, itemCount: 0 };
    case 'LOAD_CART':
      return {
        items: action.payload,
        total: calculateTotal(action.payload),
        itemCount: action.payload.length,
      };
    default:
      return state;
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, {
    items: [],
    total: 0,
    itemCount: 0,
  });

  // Load cart from localStorage on mount
  // SECURITY FIX (Audit 4 - M13): Validate and sanitize cart data from localStorage
  useEffect(() => {
    try {
      const savedCart = localStorage.getItem(CART_STORAGE_KEY);
      if (savedCart) {
        const parsed = JSON.parse(savedCart);

        // Validate it's an array
        if (!Array.isArray(parsed)) {
          console.warn('Invalid cart data in localStorage - not an array');
          localStorage.removeItem(CART_STORAGE_KEY);
          return;
        }

        // Limit number of items to prevent memory issues
        const MAX_CART_ITEMS = 100;
        if (parsed.length > MAX_CART_ITEMS) {
          console.warn(`Cart has ${parsed.length} items, limiting to ${MAX_CART_ITEMS}`);
          parsed.length = MAX_CART_ITEMS;
        }

        // Validate and sanitize each item
        const validItems: CartItem[] = [];
        for (const item of parsed) {
          const validated = validateCartItem(item);
          if (validated) {
            validItems.push(validated);
          }
        }

        if (validItems.length !== parsed.length) {
          console.warn(`Filtered ${parsed.length - validItems.length} invalid cart items`);
        }

        dispatch({ type: 'LOAD_CART', payload: validItems });
      }
    } catch (err) {
      console.error('Failed to load cart from storage:', err);
      // Clear potentially corrupted cart data
      try {
        localStorage.removeItem(CART_STORAGE_KEY);
      } catch {
        // Ignore errors clearing storage
      }
    }
  }, []);

  // Save cart to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(state.items));
    } catch (err) {
      console.error('Failed to save cart to storage:', err);
    }
  }, [state.items]);

  const addItem = (capsule: Capsule) => {
    dispatch({ type: 'ADD_ITEM', payload: capsule });
  };

  const removeItem = (capsuleId: string) => {
    dispatch({ type: 'REMOVE_ITEM', payload: capsuleId });
  };

  const clearCart = () => {
    dispatch({ type: 'CLEAR_CART' });
  };

  const isInCart = (capsuleId: string) => {
    return state.items.some(item => item.capsule.id === capsuleId);
  };

  return (
    <CartContext.Provider
      value={{
        ...state,
        addItem,
        removeItem,
        clearCart,
        isInCart,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (context === undefined) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}

export default CartContext;

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

function calculateTotal(items: CartItem[]): number {
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
  useEffect(() => {
    try {
      const savedCart = localStorage.getItem(CART_STORAGE_KEY);
      if (savedCart) {
        const items = JSON.parse(savedCart) as CartItem[];
        // Restore Date objects
        items.forEach(item => {
          item.added_at = new Date(item.added_at);
        });
        dispatch({ type: 'LOAD_CART', payload: items });
      }
    } catch (err) {
      console.error('Failed to load cart from storage:', err);
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

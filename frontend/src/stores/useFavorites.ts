/**
 * Favorites Store - Zustand
 * Manages user's favorite/pinned apps
 * Persisted to localStorage
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface FavoriteApp {
  /** Unique app identifier */
  id: string;
  /** Display name */
  name: string;
  /** Navigation path */
  path: string;
  /** Icon key (matches app card icon) */
  icon: string;
}

interface FavoritesState {
  /** List of favorited apps */
  favorites: FavoriteApp[];
  
  /** Add an app to favorites */
  addFavorite: (app: FavoriteApp) => void;
  
  /** Remove an app from favorites */
  removeFavorite: (appId: string) => void;
  
  /** Toggle favorite status */
  toggleFavorite: (app: FavoriteApp) => void;
  
  /** Check if an app is favorited */
  isFavorite: (appId: string) => boolean;
  
  /** Get favorites sorted alphabetically */
  getSortedFavorites: () => FavoriteApp[];
}

// IDs/paths of apps that have been removed/renamed and should be cleaned from favorites
const DEPRECATED_APP_IDS = [
  'knowledge-base',
  'knowledge_base', 
  'knowledgebase',
  'domains',
  'domain',
  'bi', // renamed to 'chat'
];

const DEPRECATED_PATHS = [
  '/knowledge-base',
  '/domains',
];

const isDeprecatedFavorite = (fav: FavoriteApp) => 
  DEPRECATED_APP_IDS.includes(fav.id) || 
  DEPRECATED_PATHS.some(p => fav.path.startsWith(p));

export const useFavorites = create<FavoritesState>()(
  persist(
    (set, get) => ({
      favorites: [],
      
      addFavorite: (app) => set((state) => {
        // Don't add duplicates
        if (state.favorites.some(f => f.id === app.id)) {
          return state;
        }
        return { favorites: [...state.favorites, app] };
      }),
      
      removeFavorite: (appId) => set((state) => ({
        favorites: state.favorites.filter(f => f.id !== appId)
      })),
      
      toggleFavorite: (app) => {
        const { favorites, addFavorite, removeFavorite } = get();
        if (favorites.some(f => f.id === app.id)) {
          removeFavorite(app.id);
        } else {
          addFavorite(app);
        }
      },
      
      isFavorite: (appId) => {
        return get().favorites.some(f => f.id === appId);
      },
      
      getSortedFavorites: () => {
        // Filter out deprecated apps and sort alphabetically
        return [...get().favorites]
          .filter(f => !isDeprecatedFavorite(f))
          .sort((a, b) => a.name.localeCompare(b.name));
      },
    }),
    {
      name: 'favorites-storage-v1',
      version: 2,
      migrate: (persistedState: any, version: number) => {
        // Migration: remove deprecated app favorites
        const state = persistedState as { favorites?: FavoriteApp[] };
        return {
          ...state,
          favorites: (state.favorites || []).filter(
            (f: FavoriteApp) => !isDeprecatedFavorite(f)
          ),
        };
      },
    }
  )
);

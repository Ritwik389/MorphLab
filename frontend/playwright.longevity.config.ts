import { defineConfig } from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testMatch:'lifecycle.spec.ts',timeout:3700000});

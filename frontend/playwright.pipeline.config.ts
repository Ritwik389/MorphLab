import {defineConfig} from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testMatch:'pipeline-screen.spec.ts',timeout:90000});

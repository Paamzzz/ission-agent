import { Routes } from '@angular/router';
import { inject } from '@angular/core';
import { Title } from '@angular/platform-browser';

import { Landing } from './landing/landing';
import { Analyser } from './analyser/analyser';
import { AuthCallbackComponent } from './auth/auth-callback.component';

export const routes: Routes = [
     {
          path: '',
          redirectTo: 'landing',
          pathMatch: 'full'
     },
     {
          path: 'landing',
          component: Landing,
          title: 'Ission Agent · Landing'
     },
     {
          path: 'analyzer',
          component: Analyser,
          title: 'Ission Agent · Analyzer'
     },
     {
          path: 'auth/callback',
          component: AuthCallbackComponent,
          title: 'Ission Agent · Auth'
     },
     {
          path: '**',
          redirectTo: 'landing'
     }
];

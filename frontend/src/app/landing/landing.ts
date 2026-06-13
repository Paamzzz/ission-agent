import { Component, OnInit, OnDestroy, AfterViewInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './landing.html',
  styleUrl: './landing.scss'
})
export class Landing implements OnInit, AfterViewInit, OnDestroy {

  readonly benefits = [
    {
      icon: '⚡',
      title: 'Instant Triage',
      desc: 'Skip the 30-minute investigation. Ission reads the issue and surfaces root cause in under 10 seconds.',
      stat: '10x',
      statLabel: 'faster time-to-triage',
    },
    {
      icon: '🎯',
      title: 'Precise Action Plans',
      desc: 'Not generic advice — specific, prioritized steps tailored to the codebase, labels, and issue context.',
      stat: '94%',
      statLabel: 'actionability score',
    },
    {
      icon: '🔗',
      title: 'Native GitHub Flow',
      desc: 'Analysis lands directly as a comment on the issue. Your team sees it in their existing workflow.',
      stat: '0',
      statLabel: 'context switches required',
    },
  ];

  readonly steps = [
    {
      num: '01',
      title: 'Paste the issue URL',
      desc: 'Drop any GitHub issue link. Ission fetches the full context — title, body, comments, labels.',
      tag: 'github.com/owner/repo/issues/N',
    },
    {
      num: '02',
      title: 'AI interprets the problem',
      desc: 'Gemini reads the issue with deep software engineering context, identifying root cause and affected surfaces.',
      tag: 'Gemini · FastAPI backend',
    },
    {
      num: '03',
      title: 'Structured analysis is generated',
      desc: 'A clear breakdown: root cause, affected modules, priority, risk, and a step-by-step remediation plan.',
      tag: 'JSON · Markdown · ActionPlan',
    },
    {
      num: '04',
      title: 'One click publishes to GitHub',
      desc: 'Post the full analysis as a comment directly on the issue via the GitHub API. Zero copy-paste.',
      tag: 'GitHub Octokit · REST API',
    },
  ];

  private intersectionObserver?: IntersectionObserver;

  constructor(private readonly router: Router) {}

  ngOnInit(): void {}

  ngAfterViewInit(): void {
    this.setupScrollAnimations();
  }

  goToAnalyzer(): void {
  this.router.navigate(['/analyzer']);
}

  private setupScrollAnimations(): void {
    this.intersectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).classList.add('visible');
          }
        });
      },
      { threshold: 0.1 }
    );

    document.querySelectorAll('.anim-on-scroll').forEach((el) => {
      this.intersectionObserver?.observe(el);
    });
  }

  ngOnDestroy(): void {
    this.intersectionObserver?.disconnect();
  }
}

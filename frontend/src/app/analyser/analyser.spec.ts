import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Analyser } from './analyser';

describe('Analyser', () => {
  let component: Analyser;
  let fixture: ComponentFixture<Analyser>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Analyser],
    }).compileComponents();

    fixture = TestBed.createComponent(Analyser);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

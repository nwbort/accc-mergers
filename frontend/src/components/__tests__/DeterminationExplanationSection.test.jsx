import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import DeterminationExplanationSection from '../DeterminationExplanationSection';

const withInlineReasons = (details) => ({
  events: [{
    determination_table_content: [{ item: 'Reasons for determination', details }],
  }],
});

async function expand() {
  await userEvent.click(screen.getByRole('button', { name: /Reasons for Determination/ }));
}

// The top-level <li>s, each with its nested sub-bullets (if any).
function bullets() {
  const outer = screen.getAllByRole('list')[0];
  return within(outer).getAllByRole('listitem')
    .filter((li) => li.parentElement === outer)
    .map((li) => {
      const nested = li.querySelector('ul');
      return {
        text: li.firstChild.textContent,
        children: nested ? [...nested.children].map((c) => c.textContent) : [],
      };
    });
}

describe('DeterminationExplanationSection', () => {
  it('nests "o" sub-bullets in the inline reasons under their bullet (MN-40034)', async () => {
    render(<DeterminationExplanationSection merger={withInlineReasons(
      'the ACCC makes the following findings:\n'
      + '• The Target Site is not currently used for grocery retailing.\n'
      + '• Woolworths is likely to face competition as the Target Site is located\n'
      + 'in a major growth corridor with:\n'
      + 'o alternative retail sites that are likely to be available and\n'
      + 'appropriate for rival supermarket operators, and\n'
      + 'o substantial projected population growth.\n'
      + '• Woolworths will likely have some incentive.',
    )} />);
    await expand();

    expect(bullets()).toEqual([
      { text: 'The Target Site is not currently used for grocery retailing.', children: [] },
      {
        text: 'Woolworths is likely to face competition as the Target Site is located in a major growth corridor with:',
        children: [
          'alternative retail sites that are likely to be available and appropriate for rival supermarket operators, and',
          'substantial projected population growth.',
        ],
      },
      { text: 'Woolworths will likely have some incentive.', children: [] },
    ]);
  });

  it('does not take a wrapped line starting with "of" for a sub-bullet', async () => {
    render(<DeterminationExplanationSection merger={withInlineReasons(
      'Findings:\n• the supply\nof widgets is competitive.',
    )} />);
    await expand();

    expect(bullets()).toEqual([{ text: 'the supply of widgets is competitive.', children: [] }]);
  });

  it('renders sub_items from a parsed statement of reasons', async () => {
    render(<DeterminationExplanationSection merger={{
      events: [{
        determination_statement_of_reasons: [{
          type: 'bullet_list',
          items: ['First, because:', 'Second.'],
          sub_items: [['one reason', 'another reason'], []],
        }],
      }],
    }} />);
    await expand();

    expect(bullets()).toEqual([
      { text: 'First, because:', children: ['one reason', 'another reason'] },
      { text: 'Second.', children: [] },
    ]);
  });
});

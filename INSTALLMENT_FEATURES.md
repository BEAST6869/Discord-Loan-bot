# Installment Payment Features

This document describes the installment payment features that have been added to the Discord Loan Bot.

## Available Commands

### `/pay_installment` Command

Make an installment payment towards an existing loan:

- **Usage**: `/pay_installment loan_id amount`
- **Description**: Allows captains to make partial payments towards their loans instead of paying the full amount at once.
- **Parameters**:
  - `loan_id`: The ID of the loan to pay an installment for (4-digit number)
  - `amount`: Amount to pay (must be at least the minimum installment amount)
- **Features**:
  - Shows a progress bar indicating how much of the loan has been repaid
  - Displays remaining balance after each payment
  - Tracks payment history
  - Updates loan status automatically

### `/pending_payments` Command

View all loans with pending installment payments:

- **Usage**: `/pending_payments`
- **Description**: Shows all active loans that support installment payments and their current status.
- **Features**:
  - Lists all installment loans with their payment progress
  - Shows minimum payment requirements
  - Displays due dates and payment status
  - Provides direct payment buttons for convenience

## Admin Configuration

Administrators can configure installment payment settings with the following commands:

### `/set_installment_enabled`

- **Usage**: `/set_installment_enabled [true/false]`
- **Description**: Enable or disable the installment payment feature for the server.

### `/set_min_installment_percent`

- **Usage**: `/set_min_installment_percent [percentage]`
- **Description**: Set the minimum percentage of the total loan amount that must be paid in each installment.
- **Default**: 10% of the total loan amount

## Payment Flow

1. Captain takes out a loan with installments enabled
2. Captain makes partial payments using the `/pay_installment` command
3. Bot tracks payment progress and updates remaining balance
4. Captain can view pending payments with the `/pending_payments` command
5. Once the full amount is paid, the loan is marked as repaid

## Visual Features

- **Progress Bar**: Shows completion percentage of loan repayment
- **Payment History**: Tracks all installment payments made
- **Status Updates**: Changes loan status from "active" to "active_partial" and finally to "repaid"
- **Interactive Buttons**: Allows for quick payments through UI buttons 
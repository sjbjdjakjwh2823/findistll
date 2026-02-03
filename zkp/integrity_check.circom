// Mock Circom circuit for accounting integrity checks.
// Private inputs: revenue, expenses
// Public input: net_income

pragma circom 2.0.0;

template IntegrityCheck() {
    signal input revenue;
    signal input expenses;
    signal input net_income;

    // Enforce Revenue - Expenses = Net Income
    revenue - expenses === net_income;
}

component main = IntegrityCheck();

import { expect, test } from '@playwright/test'

test('user can create and run an inline process', async ({ page }) => {
  // Arrange
  const processName = `Website builder ${Date.now()}`
  await page.goto('/')

  // Act
  await page.getByRole('button', { name: 'New process' }).click()
  await page.getByLabel('Process name').fill(processName)
  await page.getByLabel('Process type').selectOption('python')
  await page.getByLabel('Script').fill("print('frontend slice complete')")
  await page.getByRole('button', { name: 'Create process' }).click()

  const processCard = page.getByTestId('process-card').filter({
    hasText: processName,
  })
  await expect(processCard).toContainText('Inline')
  await processCard.getByRole('button', { name: 'Schedule' }).click()
  await page.getByRole('button', { name: 'Create job' }).click()

  // Assert
  const runRow = page.getByTestId('run-row').filter({
    hasText: processName,
  }).first()
  await expect(runRow).toContainText('Completed')
  await runRow.click()
  await expect(
    page.getByText('frontend slice complete', { exact: true }),
  ).toBeVisible()
})

test('user can create and run a host-file process', async ({ page }) => {
  // Arrange
  const processName = `Host workflow ${Date.now()}`
  await page.goto('/')

  // Act
  await page.getByRole('button', { name: 'New process' }).click()
  await page.getByLabel('Process name').fill(processName)
  await page.getByLabel('Process type').selectOption('python')
  await page.getByRole('button', { name: 'Host file' }).click()
  await page.getByLabel('Script path').fill('file_process.py')
  await page.getByRole('button', { name: 'Create process' }).click()

  const processCard = page.getByTestId('process-card').filter({
    hasText: processName,
  })
  await expect(processCard).toContainText('Host file')
  await expect(processCard).toContainText('file_process.py')
  await processCard.getByRole('button', { name: 'Schedule' }).click()
  await page.getByRole('button', { name: 'Create job' }).click()

  // Assert
  const runRow = page.getByTestId('run-row').filter({
    hasText: processName,
  }).first()
  await expect(runRow).toContainText('Completed')
  await runRow.click()
  await expect(
    page.getByText('frontend file source complete', { exact: true }),
  ).toBeVisible()
})

test('user can pause and resume orchestration from the dashboard', async ({ page }) => {
  // Arrange
  await page.goto('/')

  // Act
  await page.getByRole('button', { name: 'Pause scheduler' }).click()

  // Assert
  const startButton = page.getByRole('button', { name: 'Start scheduler' })
  await expect(startButton).toBeVisible()

  // Act
  await startButton.click()

  // Assert
  await expect(
    page.getByRole('button', { name: 'Pause scheduler' }),
  ).toBeVisible()
})

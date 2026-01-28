import puppeteer from 'puppeteer-core';
import { PDFDocument } from 'pdf-lib';
import fs from 'fs';
import path from 'path';

const TOTAL_SLIDES = 12;
const DECK_URL = 'http://localhost:3003/deck/';
const OUTPUT_PATH = path.resolve('Forge_Pitch_Deck.pdf');
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function generatePDF() {
  console.log('Launching Chrome...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 2 });

  console.log(`Navigating to ${DECK_URL}`);
  await page.goto(DECK_URL, { waitUntil: 'networkidle0', timeout: 30000 });

  // Wait for initial animations
  await new Promise((r) => setTimeout(r, 2000));

  const screenshots = [];

  for (let i = 0; i < TOTAL_SLIDES; i++) {
    console.log(`Capturing slide ${i + 1}/${TOTAL_SLIDES}...`);

    // Navigate to slide using keyboard
    if (i > 0) {
      await page.keyboard.press('ArrowRight');
      await new Promise((r) => setTimeout(r, 1200)); // Wait for transition
    }

    // Hide navigation bar for clean capture
    await page.evaluate(() => {
      const nav = document.querySelector('.no-print');
      if (nav) nav.style.display = 'none';
    });

    const screenshot = await page.screenshot({
      type: 'png',
      clip: { x: 0, y: 0, width: 1920, height: 1080 },
    });

    screenshots.push(screenshot);

    // Restore navigation
    await page.evaluate(() => {
      const nav = document.querySelector('.no-print');
      if (nav) nav.style.display = '';
    });
  }

  await browser.close();

  // Combine screenshots into PDF
  console.log('Building PDF...');
  const pdfDoc = await PDFDocument.create();

  for (let i = 0; i < screenshots.length; i++) {
    const img = await pdfDoc.embedPng(screenshots[i]);
    // 16:9 landscape page
    const pageWidth = 1920 * 0.5;
    const pageHeight = 1080 * 0.5;
    const pdfPage = pdfDoc.addPage([pageWidth, pageHeight]);
    pdfPage.drawImage(img, {
      x: 0,
      y: 0,
      width: pageWidth,
      height: pageHeight,
    });
  }

  const pdfBytes = await pdfDoc.save();
  fs.writeFileSync(OUTPUT_PATH, pdfBytes);
  console.log(`PDF saved to: ${OUTPUT_PATH}`);
  console.log(`File size: ${(pdfBytes.length / 1024 / 1024).toFixed(1)} MB`);
}

generatePDF().catch((err) => {
  console.error('Error:', err);
  process.exit(1);
});

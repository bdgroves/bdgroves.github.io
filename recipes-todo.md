# Recipes To Add

Queue of recipe URLs to extract once the Cloudflare Worker + extractor pipeline
is live. Each one needs to be fetched, parsed into the standard schema, and
vegetarianized where needed.

## Source list (from email, "Recipes 🌶🥦🍕")

### Cookie and Kate
- [Vegetarian Enchilada Casserole](https://cookieandkate.com/vegetarian-enchilada-casserole-recipe/)
- [Classic Minestrone Soup](https://cookieandkate.com/classic-minestrone-soup-recipe/)

### Nora Cooks
- [Recipe 5096](https://www.noracooks.com/wprm_print/5096)
- [Vegan Minestrone Soup](https://www.noracooks.com/vegan-minestrone-soup/)
- [Vegan Tiramisu](https://www.noracooks.com/vegan-tiramisu/)
- [Tofu Scramble](https://www.noracooks.com/tofu-scramble/)
- [The Best Vegan Cornbread](https://www.noracooks.com/the-best-vegan-cornbread/)

### Pizza & Bread
- [Gozney Simple Pizza Dough](https://us.gozney.com/blogs/academy/simple-pizza-dough)
- [Sugar Spun Run – Best Pizza Dough](https://sugarspunrun.com/the-best-pizza-dough-recipe/)
- [Tastemade – Frankie & Flour Homemade Bread](https://www.tastemade.com/shows/linear-struggle-meals/frankie-and-flour/recipes/homemade-bread)
- [Simply So Good – No-Knead Green Chile Cheddar Bread](https://www.simplysogood.com/no-knead-green-chile-cheddar-bread/)

### Lentils & Legumes
- [EatingWell – 7 Easy Lentil Recipes](http://www.eatingwell.com/gallery/7820467/easy-lentil-recipes/)
- [Easy Cheesy Vegetarian – Lentil Halloumi Curry](https://www.easycheesyvegetarian.com/lentil-halloumi-curry/)
- [EatingWell – Chickpea Quinoa Bowl with Roasted Red Pepper Sauce](https://www.eatingwell.com/recipe/258195/chickpea-quinoa-bowl-with-roasted-red-pepper-sauce/)

### Baking & Sweets
- [Eggless Cooking – Eggless Pancakes](https://www.egglesscooking.com/eggless-pancakes-recipe/)
- [Serious Eats – Farinata (Italian Chickpea Pancake)](https://www.seriouseats.com/recipes/2015/05/farinata-italian-chickpea-pancake-recipe.html)
- [Simple Veganista – Vegan Banana Tea Bread](https://simple-veganista.com/vegan-banana-tea-bread/)
- [Minimalist Baker – World's Easiest Cinnamon Rolls](https://minimalistbaker.com/the-worlds-easiest-cinnamon-rolls/)
- [The Comfort of Cooking – Soft Banana Snickerdoodles](https://www.thecomfortofcooking.com/2015/08/soft-banana-snickerdoodles.html)
- [Brown Eyed Baker – Salted Caramel Chocolate Chip Cookie Bars](https://www.browneyedbaker.com/salted-caramel-chocolate-chip-cookie-bars/)
- [Rabbit and Wolves – PB Chocolate Chunk Vegan Banana Bread](https://www.rhubarbarians.com/healthy-vegetarian-meal-plan-week-2-52/)
- [The Conscious Plant Kitchen – Quinoa Banana Bread](https://www.theconsciousplantkitchen.com/quinoa-banana-bread/)
- [Rabbit and Wolves – PB Chocolate Chunk Vegan Banana Bread](https://www.rabbitandwolves.com/peanut-butter-chocolate-chunk-vegan-banana-bread/)

### Pasta & Noodles
- [A Couple Cooks – Cheese Tortellini](https://www.acouplecooks.com/cheese-tortellini/)
- [Tastemade – Spicy Sesame Noodles](https://www.tastemade.com/recipes/spicy-sesame-noodles)
- [Brami – Pistachio Pesto Penne](https://enjoybrami.com/pages/pistachio-pesto-penne)
- [Brami – Pasta al Limone](https://enjoybrami.com/pages/pasta-al-limone)
- [The Stingy Vegan – Ramen Stir Fry](https://thestingyvegan.com/ramen-stir-fry/)

### Mexican & Southwest
- [I Love New Mexico – Air Fryer Tortilla Chips](https://www.ilovenewmexicoblog.com/air-fryer-tortilla-chips/)
- [The New Baguette – Plantain Nachos](https://thenewbaguette.com/plantain-nachos/)
- [Masienda – Blue Masa Harina (product, not recipe)](https://masienda.com/shop/blue-masa-harina/)

### Meal Plans / Other
- [Rhubarbarians – Healthy Vegetarian Meal Plan Week 2-52](https://www.rhubarbarians.com/healthy-vegetarian-meal-plan-week-2-52/)
- [Rhubarbarians – wprm_print 7070](https://www.rhubarbarians.com/wprm_print/7070)
- [Seattle Times Pacific Magazine – April 2006 Taste section](https://archive.seattletimes.com/archive/?date=20060414&slug=pacificptasterec16)

## Process notes

- All URLs default to **vegetarian**; check before extracting and substitute
  if any have meat/fish (the system prompt for the extractor handles this
  automatically once the Worker is up).
- Skip the Masienda link — it's a shopping page, not a recipe.
- Watch for duplicate banana-bread entries — Rhubarbarians and Rabbit & Wolves
  may overlap.

## Workflow once the extractor is live

1. Open `recipes/extract.html`
2. Paste a URL into the text field (or screenshot if the site won't fetch)
3. Click Extract → review the JSON
4. Append to `recipes.json`, commit, push
5. Cross off the URL above

## Other random notes from the email

> Chiffonade — French word for cutting strips of leafy 🥬 veggies
